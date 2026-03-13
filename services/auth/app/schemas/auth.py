from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.auth import UserRole


class BotLoginRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    bot_secret: str
    role: UserRole | None = None


class TelegramLoginData(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str
    role: UserRole | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    telegram_id: int
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
