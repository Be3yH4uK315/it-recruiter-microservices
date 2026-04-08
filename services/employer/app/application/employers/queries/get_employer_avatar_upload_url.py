from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import FileGateway, UploadUrlResult
from app.application.common.uow import UnitOfWork
from app.domain.employer.errors import EmployerNotFoundError


@dataclass(slots=True, frozen=True)
class GetEmployerAvatarUploadUrlQuery:
    employer_id: UUID
    filename: str
    content_type: str


class GetEmployerAvatarUploadUrlHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, query: GetEmployerAvatarUploadUrlQuery) -> UploadUrlResult:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(query.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {query.employer_id} not found")

        return await self._file_gateway.get_employer_avatar_upload_url(
            owner_id=query.employer_id,
            filename=query.filename,
            content_type=query.content_type,
        )
