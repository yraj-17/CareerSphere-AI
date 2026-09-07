import re
import random
import smtplib
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db, get_current_user
from app.db.models import User
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

# In-memory OTP store: { email: { "otp": str, "expires_at": datetime, "verified_token": str|None } }
# For production use Redis or a DB table instead.
_otp_store: dict = {}


def _generate_otp() -> str:
    """Generate a secure 6-digit OTP."""
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _send_otp_email(to_email: str, otp: str) -> None:
    """Send OTP via Gmail SMTP."""
    subject = "CareerSphere AI – Email Verification Code"
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#0f172a;border-radius:16px;border:1px solid #1e293b;">
      <h2 style="color:#ff8f32;margin-bottom:8px;">Verify your email</h2>
      <p style="color:#94a3b8;font-size:14px;">Use the code below to verify your CareerSphere AI account. It expires in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
      <div style="text-align:center;margin:32px 0;">
        <span style="display:inline-block;letter-spacing:12px;font-size:36px;font-weight:700;color:#ffffff;background:#1e293b;padding:16px 24px;border-radius:12px;border:1px solid #334155;">{otp}</span>
      </div>
      <p style="color:#475569;font-size:12px;text-align:center;">If you didn't request this, you can safely ignore this email.</p>
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


@router.post("/send-otp", response_model=OtpSendResponse, summary="Send OTP for email verification")
def send_otp(body: OtpSendRequest, db: Session = Depends(get_db)):
    """
    Generate and email a 6-digit OTP for the given address.
    Rejects if the email is already registered.
    """
    email = body.email.strip().lower()

    # Guard: don't send OTP to an already-registered email
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured on the server."
        )

    otp = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    _otp_store[email] = {"otp": otp, "expires_at": expires_at, "verified_token": None}

    try:
        _send_otp_email(email, otp)
    except Exception as exc:
        # Clean up so user can retry
        _otp_store.pop(email, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send verification email. Please try again. ({exc})"
        )

    return OtpSendResponse(message="Verification code sent. Please check your inbox.")


@router.post("/verify-otp", response_model=OtpVerifyResponse, summary="Verify email OTP")
def verify_otp(body: OtpVerifyRequest):
    """
    Validate the OTP for the given email.
    Returns a short-lived verification token that must be included during registration.
    """
    email = body.email.strip().lower()
    record = _otp_store.get(email)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP was requested for this email. Please request a new code."
        )

    if datetime.now(timezone.utc) > record["expires_at"]:
        _otp_store.pop(email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has expired. Please request a new one."
        )

    if body.otp != record["otp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect verification code. Please try again."
        )

    # OTP is valid – issue a short-lived verification token (HMAC-based)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(f"{email}:{token}:{settings.SECRET_KEY}".encode()).hexdigest()
    record["verified_token"] = token_hash
    record["token_raw"] = token  # keep raw to verify during registration

    return OtpVerifyResponse(
        message="Email verified successfully.",
        verification_token=token
    )


@router.get("/check-username", response_model=UsernameCheckResponse)
def check_username(
    username: str = Query(..., min_length=1, description="Username to check for availability"),
    db: Session = Depends(get_db)
):
    """
    Check if a username is available in real-time with format validation.
    """
    username = username.strip().lower()
    
    if " " in username:
        return UsernameCheckResponse(
            username=username,
            available=False,
            message="Username cannot contain spaces."
        )
    
    if not re.match(r"^[a-zA-Z0-9_.]+$", username):
        return UsernameCheckResponse(
            username=username,
            available=False,
            message="Only letters, numbers, underscore, and dot are allowed."
        )
        
    if len(username) < 3:
        return UsernameCheckResponse(
            username=username,
            available=False,
            message="Username must be at least 3 characters."
        )
        
    if len(username) > 30:
        return UsernameCheckResponse(
            username=username,
            available=False,
            message="Username must not exceed 30 characters."
        )

    # Check database
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return UsernameCheckResponse(
            username=username,
            available=False,
            message="This username is already taken."
        )

    return UsernameCheckResponse(
        username=username,
        available=True,
        message="Username is available"
    )


@router.get("/check-email", response_model=EmailCheckResponse)
def check_email(
    email: str = Query(..., min_length=1, description="Email address to check for availability"),
    db: Session = Depends(get_db)
):
    """
    Check if an email address is valid and available in real-time.
    """
    email = email.strip().lower()
    
    if " " in email:
        return EmailCheckResponse(
            email=email,
            available=False,
            message="Email address cannot contain spaces."
        )

    EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(EMAIL_REGEX, email):
        return EmailCheckResponse(
            email=email,
            available=False,
            message="Please enter a valid email address format (e.g. user@example.com)."
        )

    # Check database
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return EmailCheckResponse(
            email=email,
            available=False,
            message="An account with this email already exists."
        )

    return EmailCheckResponse(
        email=email,
        available=True,
        message="Email is available"
    )



@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    - Validates fields and password complexity.
    - Checks that the email was OTP-verified via the verification token.
    - Checks username / email uniqueness.
    - Hashes password using bcrypt.
    - Stores user in the database.
    """
    normalized_username = user_in.username.lower()
    normalized_email = user_in.email.lower()

    # 1. Validate email verification token
    record = _otp_store.get(normalized_email)
    if not record or not record.get("token_raw"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required. Please verify your email first."
        )

    expected_hash = hashlib.sha256(
        f"{normalized_email}:{record['token_raw']}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    if user_in.email_verification_token != record["token_raw"] or record["verified_token"] != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification token."
        )

    # 2. Check if username is already taken
    existing_username = db.query(User).filter(User.username == normalized_username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken."
        )

    # 3. Check if email is already taken
    existing_email = db.query(User).filter(User.email == normalized_email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please login instead."
        )

    # 4. Hash password
    hashed_pwd = hash_password(user_in.password)

    # 5. Create and save new user
    new_user = User(
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        username=normalized_username,
        email=normalized_email,
        password_hash=hashed_pwd,
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        # Clean up OTP record after successful registration
        _otp_store.pop(normalized_email, None)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user. Please try again later."
        )

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and return JWT token"
)
def login(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Log in using either username OR email and password.
    Returns JWT access token and user information.
    """
    identifier = credentials.identifier.strip().lower()
    password = credentials.password

    # Query by username OR email
    user = db.query(User).filter(
        or_(
            User.username == identifier,
            User.email == identifier
        )
    ).first()

    # Verify user existence and password hash
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT token
    access_token = create_access_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile"
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Fetch the currently authenticated user's profile details.
    """
    return current_user


@router.post(
    "/logout",
    summary="Log out the current user"
)
def logout():
    """
    Client-side token invalidation endpoint.
    """
    return {"message": "Logged out successfully"}
