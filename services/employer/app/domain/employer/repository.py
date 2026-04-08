from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.employer.entities import (
    ContactRequest,
    EmployerProfile,
    SearchDecision,
    SearchSession,
)
from app.domain.employer.value_objects import SearchSessionCandidate


class EmployerRepository(ABC):
    @abstractmethod
    async def get_by_id(self, employer_id: UUID) -> EmployerProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> EmployerProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def add(self, employer: EmployerProfile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, employer: EmployerProfile) -> None:
        raise NotImplementedError


class SearchSessionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> SearchSession | None:
        raise NotImplementedError

    @abstractmethod
    async def add(self, session: SearchSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, session: SearchSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_decision(self, session_id: UUID, decision: SearchDecision) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_employer(
        self,
        employer_id: UUID,
        *,
        limit: int = 20,
    ) -> list[SearchSession]:
        raise NotImplementedError

    @abstractmethod
    async def list_favorite_candidate_ids(self, employer_id: UUID) -> list[UUID]:
        raise NotImplementedError

    @abstractmethod
    async def list_viewed_candidate_ids(self, session_id: UUID) -> list[UUID]:
        raise NotImplementedError

    @abstractmethod
    async def list_pool_candidate_ids(self, session_id: UUID) -> list[UUID]:
        raise NotImplementedError

    @abstractmethod
    async def get_next_pool_candidate(self, session_id: UUID) -> SearchSessionCandidate | None:
        raise NotImplementedError

    @abstractmethod
    async def replace_pool(
        self,
        session_id: UUID,
        items: list[SearchSessionCandidate],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_pool_candidate_consumed(
        self,
        *,
        session_id: UUID,
        candidate_id: UUID,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_employer_statistics(self, employer_id: UUID) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    async def get_candidate_statistics(self, candidate_id: UUID) -> dict[str, int]:
        raise NotImplementedError


class ContactRequestRepository(ABC):
    @abstractmethod
    async def get_by_id(self, request_id: UUID) -> ContactRequest | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_employer_and_candidate(
        self,
        *,
        employer_id: UUID,
        candidate_id: UUID,
    ) -> ContactRequest | None:
        raise NotImplementedError

    @abstractmethod
    async def add(self, request: ContactRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, request: ContactRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_candidate(
        self,
        *,
        candidate_id: UUID,
        limit: int = 20,
    ) -> list[ContactRequest]:
        raise NotImplementedError

    @abstractmethod
    async def list_unlocked_candidate_ids(self, employer_id: UUID) -> list[UUID]:
        raise NotImplementedError
