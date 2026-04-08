from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Header, Request

os.environ["DEBUG"] = "false"
os.environ["METRICS_ENABLED"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["OTEL_TRACES_EXPORTER"] = "none"
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("SWAGGER_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")

from asgi_lifespan import LifespanManager  # type: ignore
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # type: ignore

from app.api.http.v1.dependencies import (
    get_contact_access_policy,
    get_employer_gateway,
    get_file_gateway,
    get_uow_factory,
)
from app.application.candidates.services.contact_access_policy import ContactAccessPolicy
from app.application.common.contracts import (
    DownloadUrlResult,
    EmployerGateway,
    FileGateway,
    FileMetadata,
    UploadUrlResult,
)
from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)
from app.domain.candidate.value_objects import (
    CandidateSkillVO,
    EducationItemVO,
    ExperienceItemVO,
    ProjectItemVO,
    SalaryRange,
)
from app.infrastructure.auth.internal import (
    CandidateRegistrationSubject,
    CandidateSubject,
    require_candidate_registration_subject,
    require_candidate_subject,
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


class StubEmployerGateway(EmployerGateway):
    def __init__(self) -> None:
        self._access_map: dict[tuple[str, int], bool] = {}
        self._statistics_map: dict[str, dict[str, Any]] = {}

    def allow_access(self, *, candidate_id: UUID, employer_telegram_id: int) -> None:
        self._access_map[(str(candidate_id), employer_telegram_id)] = True

    def deny_access(self, *, candidate_id: UUID, employer_telegram_id: int) -> None:
        self._access_map[(str(candidate_id), employer_telegram_id)] = False

    def set_statistics(
        self,
        *,
        candidate_id: UUID,
        profile_views: int,
        contact_requests: int,
        unlocked_contacts: int,
        is_degraded: bool = False,
    ) -> None:
        self._statistics_map[str(candidate_id)] = {
            "total_views": profile_views,
            "total_likes": unlocked_contacts,
            "total_contact_requests": contact_requests,
            "is_degraded": is_degraded,
        }

    async def has_contact_access(self, *, candidate_id: UUID, employer_telegram_id: int) -> bool:
        return self._access_map.get((str(candidate_id), employer_telegram_id), False)

    async def get_candidate_statistics(self, *, candidate_id: UUID) -> dict:
        return self._statistics_map.get(
            str(candidate_id),
            {
                "total_views": 0,
                "total_likes": 0,
                "total_contact_requests": 0,
                "is_degraded": False,
            },
        )


class StubFileGateway(FileGateway):
    def __init__(self) -> None:
        self._owner_by_file_id: dict[UUID, UUID] = {}
        self._category_by_file_id: dict[UUID, str] = {}

    async def get_avatar_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        file_id = UUID("11111111-1111-1111-1111-111111111111")
        self._owner_by_file_id[file_id] = owner_id
        self._category_by_file_id[file_id] = "candidate_avatar"
        return UploadUrlResult(
            file_id=file_id,
            upload_url=f"https://files.example/avatar/{owner_id}/{filename}",
            method="PUT",
            expires_in=3600,
            headers={"Content-Type": content_type},
        )

    async def get_resume_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        file_id = UUID("22222222-2222-2222-2222-222222222222")
        self._owner_by_file_id[file_id] = owner_id
        self._category_by_file_id[file_id] = "candidate_resume"
        return UploadUrlResult(
            file_id=file_id,
            upload_url=f"https://files.example/resume/{owner_id}/{filename}",
            method="PUT",
            expires_in=3600,
            headers={"Content-Type": content_type},
        )

    async def get_file_metadata(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        owner_id = self._owner_by_file_id.get(file_id)
        if owner_id is None:
            known_owner_ids = {
                value for value in self._owner_by_file_id.values() if value is not None
            }
            if len(known_owner_ids) == 1:
                owner_id = next(iter(known_owner_ids))

        category = self._category_by_file_id.get(file_id)
        if category is None:
            known_categories = set(self._category_by_file_id.values())
            if len(known_categories) == 1:
                category = next(iter(known_categories))
            else:
                category = "candidate_file"

        return FileMetadata(
            id=file_id,
            owner_service="candidate-service",
            owner_id=owner_id,
            category=category,
            status="active",
            filename="test.bin",
            content_type="application/octet-stream",
            size_bytes=123,
        )

    async def complete_file_upload(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        return await self.get_file_metadata(file_id=file_id)

    async def cleanup_file(
        self,
        *,
        file_id: UUID,
        reason: str,
    ) -> None:
        _ = (file_id, reason)
        return None

    async def get_file_download_url(
        self,
        *,
        file_id: UUID,
        owner_id: UUID,
    ) -> DownloadUrlResult:
        return DownloadUrlResult(
            file_id=file_id,
            download_url=f"https://files.example/download/{owner_id}/{file_id}",
            method="GET",
            expires_in=3600,
        )


class TestUnitOfWork(SqlAlchemyUnitOfWork):
    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            await self._session.close()


@pytest.fixture
def candidate_profile() -> CandidateProfile:
    return CandidateProfile.create(
        id=uuid4(),
        telegram_id=123456789,
        display_name="Дмитрий Иванов",
        headline_role="Python Developer",
        location="Paris",
        work_modes=[WorkMode.REMOTE, WorkMode.HYBRID],
        contacts_visibility=ContactsVisibility.ON_REQUEST,
        contacts={
            "email": "dmitry@example.com",
            "telegram": "@dmitry",
            "phone": "+33123456789",
        },
        status=CandidateStatus.ACTIVE,
        english_level=EnglishLevel.B2,
        about_me="Backend engineer with strong Python experience",
        salary_range=SalaryRange.from_scalars(
            salary_min=250000,
            salary_max=350000,
            currency="RUB",
        ),
        skills=[
            CandidateSkillVO(
                skill="python",
                kind=SkillKind.HARD,
                level=5,
            ),
            CandidateSkillVO(
                skill="fastapi",
                kind=SkillKind.TOOL,
                level=4,
            ),
        ],
        education=[
            EducationItemVO(
                level="bachelor",
                institution="ITMO",
                year=2020,
            ),
        ],
        experiences=[
            ExperienceItemVO(
                company="Acme",
                position="Backend Developer",
                start_date=__import__("datetime").date(2021, 1, 1),
                end_date=__import__("datetime").date(2023, 12, 31),
                responsibilities="APIs, integrations, async services",
            ),
        ],
        projects=[
            ProjectItemVO(
                title="Candidate Platform",
                description="Recruitment microservice platform",
                links=("https://example.com/project",),
            ),
        ],
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


@pytest.fixture
def employer_gateway_stub() -> StubEmployerGateway:
    return StubEmployerGateway()


@pytest.fixture
def file_gateway_stub() -> StubFileGateway:
    return StubFileGateway()


@pytest_asyncio.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    employer_gateway_stub: StubEmployerGateway,
    file_gateway_stub: StubFileGateway,
):
    import app.infrastructure.db.session as db_session
    import app.main as app_main
    from app.infrastructure.observability.telemetry import TelemetryHandle

    monkeypatch.setattr(db_session, "SessionFactory", session_factory)
    monkeypatch.setattr(app_main, "SessionFactory", session_factory)
    monkeypatch.setattr(app_main, "engine", engine)
    monkeypatch.setattr(
        app_main,
        "init_telemetry",
        lambda **_: TelemetryHandle(enabled=False, reason="disabled_for_tests"),
    )
    monkeypatch.setattr(app_main, "shutdown_telemetry", lambda *_: None)

    app = create_app()

    def override_uow_factory() -> Any:
        def factory() -> UnitOfWork:
            session = session_factory()
            return TestUnitOfWork(session)

        return factory

    def override_employer_gateway() -> EmployerGateway:
        return employer_gateway_stub

    def override_file_gateway() -> FileGateway:
        return file_gateway_stub

    def override_contact_access_policy() -> ContactAccessPolicy:
        return ContactAccessPolicy()

    def override_internal_service_auth() -> None:
        return None

    def override_candidate_registration_subject(
        x_candidate_telegram_id: str | None = Header(default=None),
    ) -> CandidateRegistrationSubject:
        telegram_id = int(x_candidate_telegram_id) if x_candidate_telegram_id else 777001
        return CandidateRegistrationSubject(
            auth_user_id=uuid4(),
            telegram_id=telegram_id,
        )

    def override_candidate_subject(
        request: Request,
        x_candidate_id: str | None = Header(default=None),
        x_candidate_telegram_id: str | None = Header(default=None),
    ) -> CandidateSubject:
        candidate_id_raw = x_candidate_id or request.path_params.get("candidate_id")
        candidate_id = (
            UUID(str(candidate_id_raw))
            if candidate_id_raw
            else UUID("00000000-0000-0000-0000-000000000000")
        )
        telegram_id = int(x_candidate_telegram_id) if x_candidate_telegram_id else 777001
        return CandidateSubject(
            auth_user_id=uuid4(),
            telegram_id=telegram_id,
            candidate_id=candidate_id,
        )

    app.dependency_overrides[get_uow_factory] = override_uow_factory
    app.dependency_overrides[get_employer_gateway] = override_employer_gateway
    app.dependency_overrides[get_file_gateway] = override_file_gateway
    app.dependency_overrides[get_contact_access_policy] = override_contact_access_policy
    app.dependency_overrides[require_internal_service] = override_internal_service_auth
    app.dependency_overrides[require_candidate_registration_subject] = (
        override_candidate_registration_subject
    )
    app.dependency_overrides[require_candidate_subject] = override_candidate_subject

    async with LifespanManager(app):
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
