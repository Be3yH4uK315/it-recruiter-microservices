from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.auth.entities import User
from app.domain.auth.value_objects import TokenPair


@dataclass(slots=True, frozen=True)
class UserView:
    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    role: str
    roles: tuple[str, ...]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserView":
        return cls(
            id=user.id,
            telegram_id=user.telegram_profile.telegram_id,
            username=user.telegram_profile.username,
            first_name=user.telegram_profile.first_name,
            last_name=user.telegram_profile.last_name,
            photo_url=user.telegram_profile.photo_url,
            role=user.role.value,
            roles=tuple(sorted(role.value for role in user.roles)),
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def to_internal_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "role": self.role,
            "roles": list(self.roles),
            "is_active": self.is_active,
        }

    def to_roles_dict(self) -> dict[str, object]:
        return {
            "user_id": self.id,
            "active_role": self.role,
            "roles": list(self.roles),
        }


@dataclass(slots=True, frozen=True)
class AuthSessionView:
    user: UserView
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

    @classmethod
    def from_domain(cls, *, user: User, token_pair: TokenPair) -> "AuthSessionView":
        return cls(
            user=UserView.from_domain(user),
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
        )
