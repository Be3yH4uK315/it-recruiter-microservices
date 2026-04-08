from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.auth.enums import UserRole


@dataclass(slots=True, frozen=True)
class TelegramProfile:
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None

    def __post_init__(self) -> None:
        if self.telegram_id <= 0:
            raise ValueError("telegram_id must be positive")

        if self.username is not None:
            object.__setattr__(self, "username", self.username.strip() or None)

        if self.first_name is not None:
            object.__setattr__(self, "first_name", self.first_name.strip() or None)

        if self.last_name is not None:
            object.__setattr__(self, "last_name", self.last_name.strip() or None)

        if self.photo_url is not None:
            object.__setattr__(self, "photo_url", self.photo_url.strip() or None)

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "photo_url": self.photo_url,
        }


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0


@dataclass(slots=True, frozen=True)
class AccessTokenClaims:
    subject: str
    telegram_id: int
    role: UserRole
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.telegram_id <= 0:
            raise ValueError("telegram_id must be positive")
        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "expires_at", self.expires_at.astimezone(timezone.utc))


@dataclass(slots=True, frozen=True)
class RefreshTokenClaims:
    subject: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))
        else:
            object.__setattr__(self, "expires_at", self.expires_at.astimezone(timezone.utc))
