from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.candidate.entities import CandidateProfile


class CandidateRepository(ABC):
    @abstractmethod
    async def get_by_id(self, candidate_id: UUID) -> CandidateProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> CandidateProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def get_many_by_ids(self, candidate_ids: list[UUID]) -> list[CandidateProfile]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, candidate: CandidateProfile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, candidate: CandidateProfile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, candidate: CandidateProfile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_for_search(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CandidateProfile]:
        raise NotImplementedError
