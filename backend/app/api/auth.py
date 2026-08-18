import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    UsernameCheckResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    - Checks username uniqueness.
    - Checks email uniqueness.
    - Hashes password using bcrypt.
    - Stores user in the database.
    """
    normalized_username = user_in.username.lower()
    normalized_email = user_in.email.lower()

    # 1. Check if username is already taken
    existing_username = db.query(User).filter(User.username == normalized_username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken."
        )

    # 2. Check if email is already taken
    existing_email = db.query(User).filter(User.email == normalized_email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please login instead."
        )

    # 3. Hash password
    hashed_pwd = hash_password(user_in.password)

    # 4. Create and save new user
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
