from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.application.auth.commands.login_via_bot import (
    LoginViaBotCommand,
    LoginViaBotHandler,
)
from app.application.auth.commands.logout import LogoutCommand, LogoutHandler
from app.application.auth.commands.logout_all import LogoutAllCommand, LogoutAllHandler
from app.application.auth.commands.refresh_session import (
    RefreshSessionCommand,
    RefreshSessionHandler,
)
from app.application.auth.services.jwt_service import JwtService
from app.application.auth.services.token_hash_service import TokenHashService
from app.config import Settings
from app.domain.auth.entities import RefreshSession, User
from app.domain.auth.enums import UserRole
from app.domain.auth.errors import InvalidRefreshTokenError, UserNotFoundError
from app.domain.auth.value_objects import TelegramProfile


class InMemoryOutbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.messages.append((routing_key, payload))


class InMemoryEventMapper:
    def map_domain_event(self, *, event, user=None, refresh_session=None) -> list[tuple[str, dict]]:
        payload = {
            "event_name": event.event_name,
            "user_id": str(user.id) if user is not None else None,
        }
        if refresh_session is not None:
            payload["session_id"] = str(refresh_session.id)
        return [(f"test.{event.event_name}", payload)]


class InMemoryUsersRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self._by_id: dict[UUID, User] = {}
        self._by_tg: dict[int, User] = {}
        for user in users or []:
            self._store(user)

    @staticmethod
    def _tg_key(user: User) -> int:
        return user.telegram_profile.telegram_id

    def _store(self, user: User) -> None:
        self._by_id[user.id] = user
        self._by_tg[self._tg_key(user)] = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self._by_tg.get(telegram_id)

    async def add(self, user: User) -> None:
        self._store(user)

    async def save(self, user: User) -> None:
        self._store(user)


class InMemoryRefreshSessionsRepo:
    def __init__(self, sessions: list[RefreshSession] | None = None) -> None:
        self._by_id: dict[UUID, RefreshSession] = {}
        self._by_hash: dict[str, RefreshSession] = {}
        for session in sessions or []:
            self._store(session)

    def _store(self, session: RefreshSession) -> None:
        self._by_id[session.id] = session
        self._by_hash[session.token_hash] = session

    async def get_by_id(self, session_id: UUID) -> RefreshSession | None:
        return self._by_id.get(session_id)

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        return self._by_hash.get(token_hash)

    async def list_by_user_id(self, user_id: UUID) -> list[RefreshSession]:
        return [s for s in self._by_id.values() if s.user_id == user_id]

    async def list_active_by_user_id(self, user_id: UUID, *, now: datetime) -> list[RefreshSession]:
        return [
            s
            for s in self._by_id.values()
            if s.user_id == user_id and (not s.revoked) and (not s.is_expired(now))
        ]

    async def add(self, session: RefreshSession) -> None:
        self._store(session)

    async def save(self, session: RefreshSession) -> None:
        self._store(session)

    async def delete(self, session_id: UUID) -> None:
        session = self._by_id.pop(session_id, None)
        if session is not None:
            self._by_hash.pop(session.token_hash, None)

    async def delete_all_by_user_id(self, user_id: UUID) -> None:
        for session in list(self._by_id.values()):
            if session.user_id == user_id:
                await self.delete(session.id)

    async def delete_expired_or_revoked_by_user_id(self, user_id: UUID, *, now: datetime) -> None:
        for session in list(self._by_id.values()):
            if session.user_id != user_id:
                continue
            if session.revoked or session.is_expired(now):
                await self.delete(session.id)


@dataclass
class InMemoryUoW:
    users: InMemoryUsersRepo
    refresh_sessions: InMemoryRefreshSessionsRepo
    outbox: InMemoryOutbox
    event_mapper: InMemoryEventMapper
    flush_count: int = 0
    commit_count: int = 0

    async def __aenter__(self) -> "InMemoryUoW":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        return None


def _settings(max_active_refresh_sessions: int = 3) -> Settings:
    return Settings(
        debug=False,
        jwt_secret_key="x" * 32,
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        refresh_token_expire_days=7,
        max_active_refresh_sessions=max_active_refresh_sessions,
    )


def _user(*, telegram_id: int = 1001, role: UserRole = UserRole.EMPLOYER) -> User:
    return User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(
            telegram_id=telegram_id,
            username=f"user_{telegram_id}",
            first_name="Test",
        ),
        role=role,
    )


def _session(
    *, user_id: UUID, token_hash: str, hours: int = 24, created_at: datetime | None = None
) -> RefreshSession:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    return RefreshSession(
        id=uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked=False,
        created_at=created_at or datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_login_via_bot_creates_user_and_tokens() -> None:
    settings = _settings(max_active_refresh_sessions=3)
    uow = InMemoryUoW(
        users=InMemoryUsersRepo(),
        refresh_sessions=InMemoryRefreshSessionsRepo(),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )

    handler = LoginViaBotHandler(
        uow_factory=lambda: uow,
        jwt_service=JwtService(settings),
        token_hash_service=TokenHashService(),
        settings=settings,
    )

    result = await handler(
        LoginViaBotCommand(
            telegram_id=1010,
            role=UserRole.EMPLOYER,
            username="alice",
            first_name="Alice",
        )
    )

    assert result.user.telegram_id == 1010
    assert result.user.role == UserRole.EMPLOYER.value
    assert result.access_token
    assert result.refresh_token
    assert uow.flush_count == 1
    assert uow.commit_count == 1
    assert len(uow.outbox.messages) >= 2


@pytest.mark.asyncio
async def test_login_via_bot_revokes_excess_sessions() -> None:
    settings = _settings(max_active_refresh_sessions=2)
    user = _user(telegram_id=2020)
    user.pull_events()

    old = _session(
        user_id=user.id,
        token_hash="old",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    keep = _session(
        user_id=user.id,
        token_hash="keep",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    uow = InMemoryUoW(
        users=InMemoryUsersRepo([user]),
        refresh_sessions=InMemoryRefreshSessionsRepo([old, keep]),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )
    handler = LoginViaBotHandler(
        uow_factory=lambda: uow,
        jwt_service=JwtService(settings),
        token_hash_service=TokenHashService(),
        settings=settings,
    )

    await handler(LoginViaBotCommand(telegram_id=2020, role=UserRole.EMPLOYER))

    assert old.revoked is True
    assert keep.revoked is False


@pytest.mark.asyncio
async def test_refresh_session_rotates_and_revokes_stale() -> None:
    settings = _settings(max_active_refresh_sessions=2)
    jwt_service = JwtService(settings)
    token_hash_service = TokenHashService()
    user = _user(telegram_id=3030, role=UserRole.CANDIDATE)
    user.pull_events()

    expires = jwt_service.build_refresh_expires_at()
    source_session_id = uuid4()
    source_token = jwt_service.create_refresh_token(
        session_id=str(source_session_id), expires_at=expires
    )
    source_session = RefreshSession.issue(
        id=source_session_id,
        user_id=user.id,
        token_hash=token_hash_service.hash_token(source_token),
        expires_at=expires,
    )
    source_session.pull_events()

    stale_session = _session(
        user_id=user.id,
        token_hash="stale-hash",
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
    )

    uow = InMemoryUoW(
        users=InMemoryUsersRepo([user]),
        refresh_sessions=InMemoryRefreshSessionsRepo([source_session, stale_session]),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )
    handler = RefreshSessionHandler(
        uow_factory=lambda: uow,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
        settings=settings,
    )

    result = await handler(RefreshSessionCommand(refresh_token=source_token))

    assert result.access_token
    assert result.refresh_token
    assert source_session.revoked is True
    assert stale_session.revoked is True
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_refresh_session_raises_for_unknown_token_hash() -> None:
    settings = _settings()
    jwt_service = JwtService(settings)
    token_hash_service = TokenHashService()

    token = jwt_service.create_refresh_token(
        session_id=str(uuid4()),
        expires_at=jwt_service.build_refresh_expires_at(),
    )

    uow = InMemoryUoW(
        users=InMemoryUsersRepo(),
        refresh_sessions=InMemoryRefreshSessionsRepo(),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )
    handler = RefreshSessionHandler(
        uow_factory=lambda: uow,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
        settings=settings,
    )

    with pytest.raises(InvalidRefreshTokenError, match="refresh session not found"):
        await handler(RefreshSessionCommand(refresh_token=token))


@pytest.mark.asyncio
async def test_logout_revokes_current_session() -> None:
    settings = _settings()
    jwt_service = JwtService(settings)
    token_hash_service = TokenHashService()
    user = _user(telegram_id=4040)
    user.pull_events()

    token = jwt_service.create_refresh_token(
        session_id=str(uuid4()),
        expires_at=jwt_service.build_refresh_expires_at(),
    )
    claims = jwt_service.decode_refresh_token(token)
    session = RefreshSession.issue(
        id=UUID(claims.subject),
        user_id=user.id,
        token_hash=token_hash_service.hash_token(token),
        expires_at=claims.expires_at,
    )
    session.pull_events()

    uow = InMemoryUoW(
        users=InMemoryUsersRepo([user]),
        refresh_sessions=InMemoryRefreshSessionsRepo([session]),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )
    handler = LogoutHandler(
        uow_factory=lambda: uow,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
    )

    await handler(LogoutCommand(refresh_token=token))

    assert session.revoked is True
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_logout_all_raises_if_user_not_found() -> None:
    uow = InMemoryUoW(
        users=InMemoryUsersRepo(),
        refresh_sessions=InMemoryRefreshSessionsRepo(),
        outbox=InMemoryOutbox(),
        event_mapper=InMemoryEventMapper(),
    )
    handler = LogoutAllHandler(uow_factory=lambda: uow)

    with pytest.raises(UserNotFoundError):
        await handler(LogoutAllCommand(user_id=uuid4()))
