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
        if not v:
            raise ValueError("Username cannot be empty.")
        v = v.strip()
        if " " in v:
            raise ValueError("Username must not contain spaces.")
        if not re.match(r"^[a-zA-Z0-9_.]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, and periods.")
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        if len(v) > 30:
            raise ValueError("Username must not exceed 30 characters.")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number.")
        return v


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

