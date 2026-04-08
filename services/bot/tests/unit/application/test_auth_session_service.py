from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.auth.services import auth_session_service as module_under_test
from app.application.common.contracts import AuthSessionView, AuthUserView
from app.infrastructure.integrations.auth_gateway import AuthGatewayUnauthorizedError

UTC = timezone.utc


def build_auth_session(
    access_token: str = "access", refresh_token: str = "refresh"
) -> AuthSessionView:
    return AuthSessionView(
        user=AuthUserView(
            id=uuid4(),
            telegram_id=1,
            username="user",
            first_name="F",
            last_name="L",
            photo_url=None,
            role="candidate",
            roles=("candidate",),
            is_active=True,
        ),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600,
    )


@dataclass
class FakeSessionModel:
    telegram_user_id: int
    is_authorized: bool
    access_token: str | None
    refresh_token: str | None
    access_token_expires_at: datetime | None
    active_role: str | None = None


class FakeBotSessionRepository:
    def __init__(self, _session) -> None:
        self.storage: dict[int, FakeSessionModel] = {}

    async def save_auth_session(
        self, *, telegram_user_id: int, auth_session: AuthSessionView
    ) -> None:
        self.storage[telegram_user_id] = FakeSessionModel(
            telegram_user_id=telegram_user_id,
            is_authorized=True,
            access_token=auth_session.access_token,
            refresh_token=auth_session.refresh_token,
            access_token_expires_at=datetime.now(UTC) + timedelta(seconds=auth_session.expires_in),
            active_role=auth_session.user.role,
        )

    async def get_by_telegram_user_id(self, telegram_user_id: int):
        return self.storage.get(telegram_user_id)

    async def clear_session(self, *, telegram_user_id: int) -> None:
        self.storage.pop(telegram_user_id, None)


class FakeAuthGateway:
    def __init__(self) -> None:
        self.login_result = build_auth_session("login_access", "login_refresh")
        self.refresh_result = build_auth_session("refreshed_access", "refreshed_refresh")
        self.logout_called_with: str | None = None
        self.raise_on_refresh_unauthorized = False
        self.raise_on_logout = False

    async def login_via_bot(self, **_kwargs) -> AuthSessionView:
        return self.login_result

    async def refresh_session(self, *, refresh_token: str) -> AuthSessionView:
        if self.raise_on_refresh_unauthorized:
            raise AuthGatewayUnauthorizedError("unauthorized")
        return self.refresh_result

    async def logout(self, *, refresh_token: str) -> None:
        self.logout_called_with = refresh_token
        if self.raise_on_logout:
            raise RuntimeError("logout failed")


@pytest.mark.asyncio
async def test_login_via_bot_saves_session(monkeypatch) -> None:
    monkeypatch.setattr(module_under_test, "BotSessionRepository", FakeBotSessionRepository)
    gateway = FakeAuthGateway()
    service = module_under_test.AuthSessionService(
        session=object(),
        auth_gateway=gateway,
        refresh_skew_seconds=30,
    )

    result = await service.login_via_bot(
        telegram_id=1,
        role="candidate",
        username="u",
        first_name="f",
        last_name="l",
        photo_url=None,
    )

    assert result.access_token == "login_access"
    assert service._repo.storage[1].refresh_token == "login_refresh"


@pytest.mark.asyncio
async def test_get_valid_access_token_refreshes_when_expiring(monkeypatch) -> None:
    monkeypatch.setattr(module_under_test, "BotSessionRepository", FakeBotSessionRepository)
    gateway = FakeAuthGateway()
    service = module_under_test.AuthSessionService(
        session=object(),
        auth_gateway=gateway,
        refresh_skew_seconds=120,
    )

    service._repo.storage[1] = FakeSessionModel(
        telegram_user_id=1,
        is_authorized=True,
        access_token="old",
        refresh_token="r1",
        access_token_expires_at=datetime.now(UTC) + timedelta(seconds=5),
        active_role="Candidate ",
    )

    token = await service.get_valid_access_token(telegram_user_id=1)
    assert token == "refreshed_access"


@pytest.mark.asyncio
async def test_get_valid_access_token_returns_none_for_unauthorized_or_missing(monkeypatch) -> None:
    monkeypatch.setattr(module_under_test, "BotSessionRepository", FakeBotSessionRepository)
    gateway = FakeAuthGateway()
    service = module_under_test.AuthSessionService(
        session=object(),
        auth_gateway=gateway,
        refresh_skew_seconds=30,
    )

    assert await service.get_valid_access_token(telegram_user_id=999) is None

    service._repo.storage[1] = FakeSessionModel(
        telegram_user_id=1,
        is_authorized=False,
        access_token="token",
        refresh_token="refresh",
        access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert await service.get_valid_access_token(telegram_user_id=1) is None


@pytest.mark.asyncio
async def test_refresh_unauthorized_clears_session(monkeypatch) -> None:
    monkeypatch.setattr(module_under_test, "BotSessionRepository", FakeBotSessionRepository)
    gateway = FakeAuthGateway()
    gateway.raise_on_refresh_unauthorized = True

    service = module_under_test.AuthSessionService(
        session=object(),
        auth_gateway=gateway,
        refresh_skew_seconds=120,
    )

    service._repo.storage[1] = FakeSessionModel(
        telegram_user_id=1,
        is_authorized=True,
        access_token="old",
        refresh_token="r1",
        access_token_expires_at=datetime.now(UTC),
    )

    token = await service.force_refresh_access_token(telegram_user_id=1)
    assert token is None
    assert 1 not in service._repo.storage


@pytest.mark.asyncio
async def test_get_active_role_normalizes_and_logout_always_clears(monkeypatch) -> None:
    monkeypatch.setattr(module_under_test, "BotSessionRepository", FakeBotSessionRepository)
    gateway = FakeAuthGateway()
    gateway.raise_on_logout = True

    service = module_under_test.AuthSessionService(
        session=object(),
        auth_gateway=gateway,
        refresh_skew_seconds=30,
    )

    service._repo.storage[1] = FakeSessionModel(
        telegram_user_id=1,
        is_authorized=True,
        access_token="t",
        refresh_token="refresh-token",
        access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        active_role=" Candidate ",
    )

    role = await service.get_active_role(telegram_user_id=1)
    assert role == "candidate"

    await service.logout(telegram_user_id=1)
    assert 1 not in service._repo.storage
