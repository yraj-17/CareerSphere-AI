import re
import json
import random
import smtplib
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.db.redis_client import get_redis
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    UsernameCheckResponse,
    EmailCheckResponse,
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Redis key prefixes
_OTP_KEY = "otp:{email}"           # stores { otp, verified_token, token_raw }
_OTP_TTL = settings.OTP_EXPIRE_MINUTES * 60   # seconds


def _generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _otp_key(email: str) -> str:
    return f"otp:{email}"


def _send_otp_email(to_email: str, otp: str) -> None:
    """Send OTP via Gmail SMTP."""
    subject = "CareerSphere AI – Email Verification Code"
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;
                background:#0f172a;border-radius:16px;border:1px solid #1e293b;">
      <h2 style="color:#ff8f32;margin-bottom:8px;">Verify your email</h2>
      <p style="color:#94a3b8;font-size:14px;">
        Use the code below to verify your CareerSphere AI account.
        It expires in {settings.OTP_EXPIRE_MINUTES} minutes.
      </p>
      <div style="text-align:center;margin:32px 0;">
        <span style="display:inline-block;letter-spacing:12px;font-size:36px;font-weight:700;
                     color:#ffffff;background:#1e293b;padding:16px 24px;border-radius:12px;
                     border:1px solid #334155;">{otp}</span>
      </div>
      <p style="color:#475569;font-size:12px;text-align:center;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(settings.EMAIL_HOST_USER, to_email, msg.as_string())


# ---------------------------------------------------------------------------
# OTP endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/send-otp",
    response_model=OtpSendResponse,
    summary="Send OTP for email verification",
)
def send_otp(
    body: OtpSendRequest,
    db: Session = Depends(get_db),
    rdb: redis_lib.Redis = Depends(get_redis),
):
    """Generate and email a 6-digit OTP. Rejects if the email is already registered."""
    email = body.email.strip().lower()

    # Guard: don't send OTP to an already-registered email
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured on the server.",
        )

    otp = _generate_otp()
    payload = json.dumps({"otp": otp, "verified_token": None, "token_raw": None})

    try:
        # Store in Redis with automatic TTL expiry
        rdb.setex(_otp_key(email), _OTP_TTL, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cache service unavailable. Please try again. ({exc})",
        )

    try:
        _send_otp_email(email, otp)
    except Exception as exc:
        rdb.delete(_otp_key(email))  # clean up so user can retry
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send verification email. Please try again. ({exc})",
        )

    return OtpSendResponse(message="Verification code sent. Please check your inbox.")


@router.post(
    "/verify-otp",
    response_model=OtpVerifyResponse,
    summary="Verify email OTP",
)
def verify_otp(
    body: OtpVerifyRequest,
    rdb: redis_lib.Redis = Depends(get_redis),
):
    """Validate the OTP and return a verification token for use during registration."""
    email = body.email.strip().lower()
    key = _otp_key(email)

    raw = rdb.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP was requested for this email, or it has expired. Please request a new code.",
        )

    record = json.loads(raw)

    if body.otp != record["otp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect verification code. Please try again.",
        )

    # Issue a short-lived verification token (HMAC-based)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    record["verified_token"] = token_hash
    record["token_raw"] = token

    # Update the record in Redis, preserving remaining TTL
    ttl = rdb.ttl(key)
    rdb.setex(key, max(ttl, 1), json.dumps(record))

    return OtpVerifyResponse(
        message="Email verified successfully.",
        verification_token=token,
    )


# ---------------------------------------------------------------------------
# Username / Email availability checks
# ---------------------------------------------------------------------------

@router.get("/check-username", response_model=UsernameCheckResponse)
def check_username(
    username: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()

    if " " in username:
        return UsernameCheckResponse(username=username, available=False,
                                     message="Username cannot contain spaces.")
    if not re.match(r"^[a-zA-Z0-9_.]+$", username):
        return UsernameCheckResponse(username=username, available=False,
                                     message="Only letters, numbers, underscore, and dot are allowed.")
    if len(username) < 3:
        return UsernameCheckResponse(username=username, available=False,
                                     message="Username must be at least 3 characters.")
    if len(username) > 30:
        return UsernameCheckResponse(username=username, available=False,
                                     message="Username must not exceed 30 characters.")

    if db.query(User).filter(User.username == username).first():
        return UsernameCheckResponse(username=username, available=False,
                                     message="This username is already taken.")

    return UsernameCheckResponse(username=username, available=True,
                                 message="Username is available")


@router.get("/check-email", response_model=EmailCheckResponse)
def check_email(
    email: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    if " " in email:
        return EmailCheckResponse(email=email, available=False,
                                  message="Email address cannot contain spaces.")
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return EmailCheckResponse(email=email, available=False,
                                  message="Please enter a valid email address format.")
    if db.query(User).filter(User.email == email).first():
        return EmailCheckResponse(email=email, available=False,
                                  message="An account with this email already exists.")

    return EmailCheckResponse(email=email, available=True, message="Email is available")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db),
    rdb: redis_lib.Redis = Depends(get_redis),
):
    normalized_username = user_in.username.lower()
    normalized_email = user_in.email.lower()
    key = _otp_key(normalized_email)

    # 1. Validate email verification token via Redis
    raw = rdb.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required. Please verify your email first.",
        )

    record = json.loads(raw)
    if not record.get("token_raw"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required. Please verify your email first.",
        )

    expected_hash = hashlib.sha256(
        f"{normalized_email}:{record['token_raw']}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    if (
        user_in.email_verification_token != record["token_raw"]
        or record["verified_token"] != expected_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification token.",
        )

    # 2. Uniqueness checks
    if db.query(User).filter(User.username == normalized_username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This username is already taken.")
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="An account with this email already exists. Please login instead.")

    # 3. Create user
    new_user = User(
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        username=normalized_username,
        email=normalized_email,
        password_hash=hash_password(user_in.password),
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        rdb.delete(key)  # clean up OTP record
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user. Please try again later.",
        )

    return new_user


# ---------------------------------------------------------------------------
# Login / Me / Logout
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and return JWT token",
)
def login(credentials: UserLoginRequest, db: Session = Depends(get_db)):
    identifier = credentials.identifier.strip().lower()

    user = db.query(User).filter(
        or_(User.username == identifier, User.email == identifier)
    ).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(subject=user.id),
        token_type="bearer",
        user=user,
    )


@router.get("/me", response_model=UserResponse, summary="Get current authenticated user")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", summary="Log out the current user")
def logout():
    return {"message": "Logged out successfully"}
