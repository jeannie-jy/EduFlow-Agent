"""Pydantic contracts for the email and password authentication API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from security.passwords import validate_password_policy


class RegisterRequest(BaseModel):
    """Input required to create a new email/password account."""

    email: EmailStr
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(
        json_schema_extra={"minLength": 8, "maxLength": 128, "x-max-bytes": 256}
    )

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> object:
        """Strip presentation whitespace before applying length constraints."""
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def validate_registration_password(cls, value: str) -> str:
        """Use the shared backend password policy for registrations."""
        return validate_password_policy(value)


class LoginRequest(BaseModel):
    """Credentials accepted by the login endpoint."""

    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
        json_schema_extra={"x-max-bytes": 256},
    )

    @field_validator("password")
    @classmethod
    def validate_login_password_size(cls, value: str) -> str:
        """Reject oversized login input without applying registration policy."""
        if len(value.encode("utf-8")) > 256:
            raise ValueError("密码编码后不能超过 256 字节")
        return value


class UserResponse(BaseModel):
    """Public, non-sensitive representation of an authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nickname: str
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Access-token response returned by successful authentication flows."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
