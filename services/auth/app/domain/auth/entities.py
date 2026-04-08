from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from app.domain.auth.enums import AuthProvider, UserRole
from app.domain.auth.errors import UserInactiveError
from app.domain.auth.value_objects import TelegramProfile
from app.domain.common.events import DomainEvent


@dataclass(slots=True, frozen=True)
class UserRegistered(DomainEvent):
    user_id: UUID | None = None
    telegram_id: int | None = None
    role: str | None = None


@dataclass(slots=True, frozen=True)
class UserAuthenticated(DomainEvent):
    user_id: UUID | None = None
    telegram_id: int | None = None
    provider: str | None = None
    role: str | None = None


@dataclass(slots=True, frozen=True)
class UserRoleChanged(DomainEvent):
    user_id: UUID | None = None
    telegram_id: int | None = None
    old_role: str | None = None
    new_role: str | None = None


@dataclass(slots=True, frozen=True)
class RefreshSessionIssued(DomainEvent):
    session_id: UUID | None = None
    user_id: UUID | None = None
    expires_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class RefreshSessionRevoked(DomainEvent):
    session_id: UUID | None = None
    user_id: UUID | None = None


@dataclass(slots=True)
class User:
    id: UUID
    telegram_profile: TelegramProfile
    role: UserRole
    roles: frozenset[UserRole] = field(default_factory=frozenset)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.created_at = self._normalize_datetime(self.created_at)
        self.updated_at = self._normalize_datetime(self.updated_at)

        normalized_roles = frozenset(self.roles) if self.roles else frozenset({self.role})
        if self.role not in normalized_roles:
            normalized_roles = frozenset({*normalized_roles, self.role})
        self.roles = normalized_roles

    @classmethod
    def register(
        cls,
        *,
        id: UUID,
        telegram_profile: TelegramProfile,
        role: UserRole,
    ) -> "User":
        user = cls(
            id=id,
            telegram_profile=telegram_profile,
            role=role,
            roles=frozenset({role}),
            is_active=True,
        )
        user._events.append(
            UserRegistered(
                user_id=user.id,
                telegram_id=user.telegram_profile.telegram_id,
                role=user.role.value,
            )
        )
        return user

    def ensure_active(self) -> None:
        if not self.is_active:
            raise UserInactiveError("user is inactive")

    def update_telegram_profile(self, telegram_profile: TelegramProfile) -> None:
        merged_profile = TelegramProfile(
            telegram_id=self.telegram_profile.telegram_id,
            username=(
                telegram_profile.username
                if telegram_profile.username is not None
                else self.telegram_profile.username
            ),
            first_name=(
                telegram_profile.first_name
                if telegram_profile.first_name is not None
                else self.telegram_profile.first_name
            ),
            last_name=(
                telegram_profile.last_name
                if telegram_profile.last_name is not None
                else self.telegram_profile.last_name
            ),
            photo_url=(
                telegram_profile.photo_url
                if telegram_profile.photo_url is not None
                else self.telegram_profile.photo_url
            ),
        )

        if merged_profile == self.telegram_profile:
            return

        self.telegram_profile = merged_profile
        self.touch()

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles

    def bind_role(self, role: UserRole) -> None:
        if role in self.roles:
            return
        self.roles = frozenset({*self.roles, role})
        self.touch()

    def change_role(self, role: UserRole) -> None:
        self.bind_role(role)

        if self.role == role:
            return

        previous = self.role
        self.role = role
        self.touch()
        self._events.append(
            UserRoleChanged(
                user_id=self.id,
                telegram_id=self.telegram_profile.telegram_id,
                old_role=previous.value,
                new_role=role.value,
            )
        )

    def mark_authenticated(self, provider: AuthProvider) -> None:
        self.ensure_active()
        self.touch()
        self._events.append(
            UserAuthenticated(
                user_id=self.id,
                telegram_id=self.telegram_profile.telegram_id,
                provider=provider.value,
                role=self.role.value,
            )
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


@dataclass(slots=True)
class RefreshSession:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.expires_at = self._normalize_datetime(self.expires_at)
        self.created_at = self._normalize_datetime(self.created_at)

    @classmethod
    def issue(
        cls,
        *,
        id: UUID,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> "RefreshSession":
        session = cls(
            id=id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        session._events.append(
            RefreshSessionIssued(
                session_id=session.id,
                user_id=session.user_id,
                expires_at=session.expires_at,
            )
        )
        return session

    def revoke(self) -> None:
        if self.revoked:
            return

        self.revoked = True
        self._events.append(
            RefreshSessionRevoked(
                session_id=self.id,
                user_id=self.user_id,
            )
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        else:
            reference = reference.astimezone(timezone.utc)
        return self.expires_at <= reference

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
