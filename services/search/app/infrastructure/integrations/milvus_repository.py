from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.search.repository import VectorSearchRepository
from app.infrastructure.integrations.milvus_client import MilvusClientWrapper


@dataclass(slots=True)
class MilvusCandidateRepository(VectorSearchRepository):
    client: MilvusClientWrapper

    async def clear_all(self) -> None:
        await self.client.reset_collection()

    async def list_candidate_ids(self) -> list[str]:
        return await self.client.list_candidate_ids()

    async def search_candidate_ids(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list[UUID],
        limit: int,
    ) -> list[str]:
        if not query_vector:
            return []

        hits = await self.client.search(
            query_vector=query_vector,
            exclude_ids=[str(value) for value in exclude_ids],
            top_k=limit,
        )
        return [str(item["candidate_id"]) for item in hits]

    async def upsert_vector(
        self,
        *,
        candidate_id: UUID,
        embedding: list[float],
    ) -> None:
        if not embedding:
            return
        await self.client.insert([str(candidate_id)], [embedding])

    async def upsert_vectors(
        self,
        *,
        candidate_ids: list[UUID],
        embeddings: list[list[float]],
    ) -> None:
        ids: list[str] = []
        vectors: list[list[float]] = []

        for candidate_id, embedding in zip(candidate_ids, embeddings, strict=False):
            if not embedding:
                continue
            ids.append(str(candidate_id))
            vectors.append(embedding)

        if not ids:
            return

        await self.client.insert(ids, vectors)

    async def delete_vector(self, *, candidate_id: UUID) -> None:
        await self.client.delete(str(candidate_id))

    async def has_vector(self, *, candidate_id: UUID) -> bool:
        return await self.client.has_vector(str(candidate_id))
