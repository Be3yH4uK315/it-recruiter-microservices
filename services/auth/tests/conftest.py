from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager  # type: ignore
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # type: ignore

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ["DEBUG"] = "false"
os.environ["METRICS_ENABLED"] = "false"
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("SWAGGER_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("IDEMPOTENCY_ENABLED", "true")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("RABBITMQ_EXCHANGE", "auth.events")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-characters")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("MAX_ACTIVE_REFRESH_SESSIONS", "5")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-telegram-bot-token")
os.environ.setdefault("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_auth"
)

from app.api.http.v1.dependencies import get_uow_factory
from app.application.common.uow import UnitOfWork
from app.infrastructure.db.base import Base
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.main import create_app


def _run_integration_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION", "").strip().lower() in {"1", "true", "yes", "on"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _run_integration_enabled():
        return

    skip_integration = pytest.mark.skip(
        reason="integration tests are disabled by default; set RUN_INTEGRATION=1",
    )
    for item in items:
        if "/tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(skip_integration)


class TestUnitOfWork(SqlAlchemyUnitOfWork):
    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            await self._session.close()


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    container = PostgresContainer("postgres:16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def postgres_url(postgres_container: PostgresContainer) -> str:
    sync_url = postgres_container.get_connection_url()
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest_asyncio.fixture
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    import app.infrastructure.db.models.auth  # noqa: F401

    engine = create_async_engine(postgres_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
):
    import app.infrastructure.db.session as db_session
    import app.main as app_main
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(db_session, "SessionFactory", session_factory)
    monkeypatch.setattr(app_main, "engine", engine)

    app = create_app()

    def override_uow_factory() -> Any:
        def factory() -> UnitOfWork:
            session = session_factory()
            return TestUnitOfWork(session)

        return factory

    app.dependency_overrides[get_uow_factory] = override_uow_factory

    async with LifespanManager(app):
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def internal_client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={
            "Authorization": "Bearer test-internal-token",
        },
    ) as client:
        yield client


@pytest.fixture
def bot_login_payload() -> dict[str, Any]:
    return {
        "telegram_id": 1001,
        "role": "employer",
        "username": "acme_hr",
        "first_name": "Alice",
        "last_name": "HR",
        "photo_url": "https://example.com/avatar.jpg",
    }


@pytest_asyncio.fixture
async def bot_login(
    internal_client: httpx.AsyncClient,
    bot_login_payload: dict[str, Any],
) -> Callable[..., Any]:
    async def _login(**overrides: Any) -> dict[str, Any]:
        payload = {**bot_login_payload, **overrides}
        response = await internal_client.post("/api/v1/auth/login/bot", json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    return _login
