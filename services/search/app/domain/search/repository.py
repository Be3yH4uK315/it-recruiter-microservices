from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class LexicalSearchRepository(ABC):
    @abstractmethod
    async def clear_all(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_candidate_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def search_candidate_ids(self, *, filters: dict, limit: int) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def count_candidates(self, *, filters: dict) -> int:
        raise NotImplementedError

    @abstractmethod
    async def get_documents(self, candidate_ids: list[str]) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_document(self, candidate_id: UUID) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_document(self, *, candidate_id: UUID, document: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_document(self, *, candidate_id: UUID) -> None:
        raise NotImplementedError


class VectorSearchRepository(ABC):
    @abstractmethod
    async def clear_all(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_candidate_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def search_candidate_ids(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list[UUID],
        limit: int,
    ) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def upsert_vector(
        self,
        *,
        candidate_id: UUID,
        embedding: list[float],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_vector(self, *, candidate_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def has_vector(self, *, candidate_id: UUID) -> bool:
        raise NotImplementedError
