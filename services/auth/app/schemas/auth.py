from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.auth.enums import UserRole


class TelegramAuthPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: str
    hash: str

    @field_validator("id", "auth_date", "hash")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("first_name", "last_name", "username", "photo_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class BotLoginRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_id: int = Field(..., gt=0)
    role: UserRole
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None

    @field_validator("username", "first_name", "last_name", "photo_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TelegramLoginRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole
    auth_payload: TelegramAuthPayloadSchema


class RefreshRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("refresh_token must not be empty")
        return normalized


class LogoutRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("refresh_token must not be empty")
        return normalized


class VerifyAccessTokenRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(..., min_length=1)

    @field_validator("access_token")
    @classmethod
    def validate_access_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("access_token must not be empty")
        return normalized


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    role: str
    roles: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthSessionResponseSchema(BaseModel):
    user: UserResponseSchema
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class InternalUserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    role: str
    roles: list[str]
    is_active: bool


class TokenVerificationResponseSchema(BaseModel):
    user_id: UUID
    telegram_id: int
    role: str
    roles: list[str]
    is_active: bool
    expires_at: datetime


class UserRolesResponseSchema(BaseModel):
    user_id: UUID
    active_role: str
    roles: list[str]
