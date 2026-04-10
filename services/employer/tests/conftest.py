from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("SWAGGER_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("IDEMPOTENCY_ENABLED", "true")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("RABBITMQ_EXCHANGE", "app.events")
os.environ.setdefault("CANDIDATE_SERVICE_URL", "http://candidate-service")
os.environ.setdefault("SEARCH_SERVICE_URL", "http://search-service")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
)
os.environ.setdefault("METRICS_ENABLED", "false")

from asgi_lifespan import LifespanManager  # type: ignore
from fastapi import Header
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # type: ignore

from app.api.http.v1.dependencies import (
    get_candidate_gateway,
    get_search_gateway,
    get_uow_factory,
)
from app.application.common.contracts import (
    CandidateGateway,
    CandidateIdentity,
    CandidateShortProfile,
    SearchCandidatesBatchResult,
    SearchGateway,
)
from app.application.common.uow import UnitOfWork
from app.domain.employer.enums import WorkMode
from app.infrastructure.auth.internal import (
    CandidateSubject,
    require_candidate_subject,
    require_employer_subject,
    require_internal_service,
)
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


class StubCandidateGateway(CandidateGateway):
    def __init__(self) -> None:
        self._profiles: dict[str, CandidateShortProfile] = {}

    def add_profile(self, profile: CandidateShortProfile) -> None:
        self._profiles[str(profile.id)] = profile

    async def get_candidate_profile(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> CandidateShortProfile | None:
        return self._profiles.get(str(candidate_id))

    async def get_candidate_identity(
        self,
        *,
        telegram_id: int,
    ) -> CandidateIdentity | None:
        profile = next(iter(self._profiles.values()), None)
        if profile is None:
            return None
        return CandidateIdentity(
            candidate_id=profile.id,
            telegram_id=telegram_id,
            status=profile.status,
        )


class StubSearchGateway(SearchGateway):
    def __init__(self) -> None:
        self._results: dict[tuple[str, int, int], SearchCandidatesBatchResult] = {}

    @staticmethod
    def _normalize_filters(filters: dict) -> str:
        return json.dumps(filters, sort_keys=True, ensure_ascii=False)

    def set_result(
        self,
        *,
        filters: dict,
        limit: int,
        offset: int,
        result: SearchCandidatesBatchResult,
    ) -> None:
        self._results[(self._normalize_filters(filters), limit, offset)] = result

    async def search_candidates(
        self,
        *,
        filters: dict,
        limit: int,
        include_total: bool = True,
        offset: int = 0,
    ) -> SearchCandidatesBatchResult:
        return self._results.get(
            (self._normalize_filters(filters), limit, offset),
            SearchCandidatesBatchResult(total=0, items=[]),
        )


class TestUnitOfWork(SqlAlchemyUnitOfWork):
    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            await self._session.close()


@pytest.fixture
def candidate_gateway_stub() -> StubCandidateGateway:
    return StubCandidateGateway()


@pytest.fixture
def search_gateway_stub() -> StubSearchGateway:
    return StubSearchGateway()


@pytest.fixture
def employer_payload() -> dict[str, Any]:
    return {
        "telegram_id": 1001,
        "company": "Acme",
        "contacts": {
            "email": "hr@acme.test",
            "telegram": "@acme_hr",
        },
    }


@pytest.fixture
def candidate_short_profile() -> CandidateShortProfile:
    candidate_id = uuid4()
    return CandidateShortProfile(
        id=candidate_id,
        display_name="Дмитрий Иванов",
        headline_role="Python Developer",
        location="Paris",
        work_modes=[WorkMode.REMOTE.value, WorkMode.HYBRID.value],
        experience_years=4.5,
        skills=[
            {"skill": "python", "level": 5},
            {"skill": "fastapi", "level": 4},
        ],
        salary_min=250000,
        salary_max=350000,
        currency="RUB",
        english_level="B2",
        contacts_visibility="on_request",
        contacts={"email": "dmitry@example.com", "telegram": "@dmitry"},
        about_me="Backend engineer",
        explanation={"rrf": 0.91},
        match_score=0.93,
    )


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
async def engine(postgres_url: str) -> AsyncEngine:  # type: ignore
    import app.infrastructure.db.models.employer  # noqa: F401

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
    candidate_gateway_stub: StubCandidateGateway,
    search_gateway_stub: StubSearchGateway,
):
    import app.infrastructure.db.session as db_session
    import app.main as app_main
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(db_session, "SessionFactory", session_factory)
    monkeypatch.setattr(app_main, "SessionFactory", session_factory)
    monkeypatch.setattr(app_main, "engine", engine)

    app = create_app()

    def override_uow_factory() -> Any:
        def factory() -> UnitOfWork:
            session = session_factory()
            return TestUnitOfWork(session)

        return factory

    def override_candidate_gateway() -> CandidateGateway:
        return candidate_gateway_stub

    def override_search_gateway() -> SearchGateway:
        return search_gateway_stub

    def override_internal_service_auth() -> None:
        return None

    def override_employer_subject(
        x_employer_telegram_id: str | None = Header(default=None),
    ) -> int:
        if x_employer_telegram_id is None:
            return 1001
        return int(x_employer_telegram_id)

    def override_candidate_subject() -> CandidateSubject:
        profile = next(iter(candidate_gateway_stub._profiles.values()), None)
        candidate_id = profile.id if profile is not None else uuid4()
        return CandidateSubject(
            auth_user_id=uuid4(),
            telegram_id=777001,
            candidate_id=candidate_id,
        )

    app.dependency_overrides[get_uow_factory] = override_uow_factory
    app.dependency_overrides[get_candidate_gateway] = override_candidate_gateway
    app.dependency_overrides[get_search_gateway] = override_search_gateway
    app.dependency_overrides[require_internal_service] = override_internal_service_auth
    app.dependency_overrides[require_employer_subject] = override_employer_subject
    app.dependency_overrides[require_candidate_subject] = override_candidate_subject

    async with LifespanManager(app):
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={
            "Authorization": "Bearer test-internal-token",
            "X-Employer-Telegram-Id": "1001",
        },
    ) as client:
        yield client


@pytest_asyncio.fixture
async def client_without_auth(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
