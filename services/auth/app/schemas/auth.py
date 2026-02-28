from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID

from app.models.auth import UserRole

class BotLoginRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    bot_secret: str

class TelegramLoginData(BaseModel):
    """
    Данные, которые приходят от Telegram.
    """
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

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