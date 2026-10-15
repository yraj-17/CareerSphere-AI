import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class OtpSendRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to send OTP to")


class OtpSendResponse(BaseModel):
    message: str


class OtpVerifyRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address the OTP was sent to")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class OtpVerifyResponse(BaseModel):
    message: str
    verification_token: str


class UserRegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")
    username: str = Field(..., min_length=3, max_length=30, description="Unique username")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="User password")
    email_verification_token: str = Field(..., description="Token received after OTP verification")

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_names(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty.")
        return v.strip()

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return normalize_username(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


def normalize_username(value: str) -> str:
    if not value:
        raise ValueError("Username cannot be empty.")
    value = value.strip()
    if " " in value:
        raise ValueError("Username must not contain spaces.")
    if not re.match(r"^[a-zA-Z0-9_.]+$", value):
        raise ValueError("Username can only contain letters, numbers, underscores, and periods.")
    if len(value) < 3:
        raise ValueError("Username must be at least 3 characters long.")
    if len(value) > 30:
        raise ValueError("Username must not exceed 30 characters.")
    return value.lower()


def validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", value):
        raise ValueError("Password must contain at least one number.")
    return value


class UserAccountUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=30)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_optional_names(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value

    @field_validator("username", mode="before")
    @classmethod
    def validate_account_username(cls, value):
        if value is None:
            return None
        return normalize_username(value)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserLoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, description="Username or Email")
    password: str = Field(..., min_length=1, description="Password")

    @field_validator("identifier", mode="before")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Username or Email is required.")
        return v.strip()


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    username: str
    email: str
    profile_photo_url: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UsernameCheckResponse(BaseModel):
    username: str
    available: bool
    message: str


class EmailCheckResponse(BaseModel):
    email: str
    available: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    message: str
    service: str = "CareerSphere AI Backend"
    postgres: Optional[str] = None
    redis: Optional[str] = None
    qdrant: Optional[str] = None
    minio: Optional[str] = None

