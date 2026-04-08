from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import FileGateway, UploadUrlResult
from app.application.common.uow import UnitOfWork
from app.domain.candidate.enums import CandidateStatus
from app.domain.candidate.errors import CandidateBlockedError, CandidateNotFoundError


@dataclass(slots=True, frozen=True)
class GetResumeUploadUrlQuery:
    candidate_id: UUID
    filename: str
    content_type: str


class GetResumeUploadUrlHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, query: GetResumeUploadUrlQuery) -> UploadUrlResult:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(query.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {query.candidate_id} not found")

            if candidate.status == CandidateStatus.BLOCKED:
                raise CandidateBlockedError("candidate is blocked")

        return await self._file_gateway.get_resume_upload_url(
            owner_id=query.candidate_id,
            filename=query.filename,
            content_type=query.content_type,
        )
