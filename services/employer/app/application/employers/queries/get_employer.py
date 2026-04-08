from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.contracts import FileGateway
from app.application.common.uow import UnitOfWork
from app.application.employers.dto.views import EmployerView
from app.domain.employer.entities import EmployerProfile
from app.domain.employer.errors import EmployerNotFoundError


class _EmployerViewBuilder:
    def __init__(self, file_gateway: FileGateway) -> None:
        self._file_gateway = file_gateway

    async def build(self, employer: EmployerProfile) -> EmployerView:
        base_view = EmployerView.from_entity(employer)

        avatar_download_url = None
        if base_view.avatar_file_id is not None:
            avatar_result = await self._file_gateway.get_download_url(
                file_id=base_view.avatar_file_id,
                owner_id=base_view.id,
            )
            avatar_download_url = avatar_result.download_url

        document_download_url = None
        if base_view.document_file_id is not None:
            document_result = await self._file_gateway.get_download_url(
                file_id=base_view.document_file_id,
                owner_id=base_view.id,
            )
            document_download_url = document_result.download_url

        return EmployerView(
            id=base_view.id,
            telegram_id=base_view.telegram_id,
            company=base_view.company,
            contacts=base_view.contacts,
            avatar_file_id=base_view.avatar_file_id,
            avatar_download_url=avatar_download_url,
            document_file_id=base_view.document_file_id,
            document_download_url=document_download_url,
            created_at=base_view.created_at,
            updated_at=base_view.updated_at,
        )


class GetEmployerHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._view_builder = _EmployerViewBuilder(file_gateway)

    async def __call__(self, employer_id: UUID) -> EmployerView:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {employer_id} not found")

        return await self._view_builder.build(employer)


class GetEmployerByTelegramHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._view_builder = _EmployerViewBuilder(file_gateway)

    async def __call__(self, telegram_id: int) -> EmployerView:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_telegram_id(telegram_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer with telegram_id={telegram_id} not found")

        return await self._view_builder.build(employer)
