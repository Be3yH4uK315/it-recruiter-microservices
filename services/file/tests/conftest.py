from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

os.environ["DEBUG"] = "false"
os.environ["METRICS_ENABLED"] = "false"
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("SWAGGER_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("APP_ENV", "test")

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # type: ignore

from app.api.http.v1.dependencies import (
    get_settings_dependency,
    get_storage,
    get_uow_factory,
)
from app.application.common.contracts import ObjectStorage
from app.application.common.uow import UnitOfWork
from app.config import Settings, get_settings
from app.infrastructure.auth.internal import require_internal_service
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_async_session
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
    skip_db_container = pytest.mark.skip(
        reason="docker-backed db tests are disabled by default; set RUN_INTEGRATION=1",
    )
    docker_fixtures = {
        "postgres_container",
        "postgres_url",
        "engine",
        "session_factory",
        "db_session",
    }
    for item in items:
        if "/tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(skip_integration)
            continue
        if docker_fixtures.intersection(set(getattr(item, "fixturenames", ()))):
            item.add_marker(skip_db_container)


class StubObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        self.upload_urls: list[dict[str, Any]] = []
        self.download_urls: list[dict[str, Any]] = []
        self.deleted_keys: list[str] = []
        self.existing_keys: set[str] = set()
        self.bucket_ensured = False

    async def ensure_bucket_exists(self) -> None:
        self.bucket_ensured = True

    async def generate_presigned_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        self.upload_urls.append(
            {
                "object_key": object_key,
                "content_type": content_type,
                "expires_in": expires_in,
            }
        )
        self.existing_keys.add(object_key)
        return f"https://files.example/upload/{object_key}"

    async def generate_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in: int,
    ) -> str:
        self.download_urls.append(
            {
                "object_key": object_key,
                "expires_in": expires_in,
            }
        )
        return f"https://files.example/download/{object_key}"

    async def delete_object(self, *, object_key: str) -> None:
        self.deleted_keys.append(object_key)
        self.existing_keys.discard(object_key)

    async def object_exists(self, *, object_key: str) -> bool:
        return object_key in self.existing_keys

    async def get_object_size(self, *, object_key: str) -> int | None:
        if object_key not in self.existing_keys:
            return None
        return 1024


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
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def storage_stub() -> StubObjectStorage:
    return StubObjectStorage()


@pytest.fixture
def settings_override(postgres_url: str) -> Settings:
    settings = get_settings().model_copy(deep=True)
    settings.database_url = postgres_url
    settings.internal_service_token = "test-internal-token"
    settings.swagger_enabled = False
    settings.log_json = False
    settings.s3_bucket_name = "files"
    settings.s3_public_endpoint_url = "https://files.example"
    settings.ngrok_api_url = None
    settings.default_upload_url_expiration_seconds = 3600
    settings.default_download_url_expiration_seconds = 3600
    return settings


@pytest_asyncio.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    storage_stub: StubObjectStorage,
    settings_override: Settings,
):
    import app.main as app_main

    monkeypatch.setattr(app_main, "get_settings", lambda: settings_override)
    monkeypatch.setattr(app_main, "S3ObjectStorage", lambda settings: storage_stub)
    monkeypatch.setattr(app_main, "SessionFactory", session_factory)

    app = create_app()

    def override_uow_factory() -> Any:
        def factory() -> UnitOfWork:
            session = session_factory()
            return TestUnitOfWork(session)

        return factory

    def override_storage() -> ObjectStorage:
        return storage_stub

    def override_settings() -> Settings:
        return settings_override

    async def override_async_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def override_internal_service_auth() -> None:
        return None

    app.dependency_overrides[get_uow_factory] = override_uow_factory
    app.dependency_overrides[get_storage] = override_storage
    app.dependency_overrides[get_settings_dependency] = override_settings
    app.dependency_overrides[get_async_session] = override_async_session
    app.dependency_overrides[require_internal_service] = override_internal_service_auth

    async with app.router.lifespan_context(app):
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver/api/v1",
        headers={"Authorization": "Bearer test-internal-token"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def client_without_auth(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver/api/v1",
    ) as client:
        yield client
