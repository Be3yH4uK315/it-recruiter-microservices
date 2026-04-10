from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import (
    CandidateGateway,
    CandidateIndexingService,
)
from app.application.search.dto.views import RebuildIndicesView
from app.domain.search.repository import (
    LexicalSearchRepository,
    VectorSearchRepository,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

_INACTIVE_STATUSES = {"hidden", "blocked", "deleted", "inactive"}


@dataclass(slots=True, frozen=True)
class RebuildIndicesCommand:
    batch_size: int = 100


class RebuildIndicesHandler:
    def __init__(
        self,
        candidate_gateway: CandidateGateway,
        indexing_service: CandidateIndexingService,
        lexical_repository: LexicalSearchRepository,
        vector_repository: VectorSearchRepository,
    ) -> None:
        self._candidate_gateway = candidate_gateway
        self._indexing_service = indexing_service
        self._lexical_repository = lexical_repository
        self._vector_repository = vector_repository

    async def __call__(self, command: RebuildIndicesCommand) -> RebuildIndicesView:
        processed = 0
        indexed = 0
        skipped = 0
        failed = 0
        offset = 0
        active_candidate_ids: set[UUID] = set()
        completed_full_scan = False

        while True:
            batch = await self._candidate_gateway.list_candidates(
                limit=command.batch_size,
                offset=offset,
            )
            if not batch:
                completed_full_scan = True
                break

            vectors_to_upsert: list[tuple[UUID, list[float]]] = []

            for payload in batch:
                processed += 1
                active_candidate_ids.add(payload.id)
                try:
                    normalized_status = (payload.status or "").strip().lower()
                    if normalized_status in _INACTIVE_STATUSES:
                        await self._lexical_repository.delete_document(candidate_id=payload.id)
                        await self._vector_repository.delete_vector(candidate_id=payload.id)
                        skipped += 1
                        continue

                    indexed_document = await self._indexing_service.build_indexed_document(
                        payload=payload,
                    )
                    await self._lexical_repository.upsert_document(
                        candidate_id=indexed_document.candidate_id,
                        document=indexed_document.document,
                    )
                    vectors_to_upsert.append(
                        (
                            indexed_document.candidate_id,
                            indexed_document.embedding,
                        )
                    )
                    indexed += 1
                except Exception as exc:
                    failed += 1
                    logger.exception(
                        "candidate reindex failed",
                        extra={
                            "candidate_id": str(payload.id),
                            "display_name": payload.display_name,
                            "error_type": exc.__class__.__name__,
                        },
                        exc_info=exc,
                    )

            failed += await self._upsert_vectors_batch(vectors_to_upsert)

            if len(batch) < command.batch_size:
                completed_full_scan = True
                break

            offset += command.batch_size

        if completed_full_scan:
            await self._delete_orphaned_documents(active_candidate_ids)

        return RebuildIndicesView(
            processed=processed,
            indexed=indexed,
            skipped=skipped,
            failed=failed,
        )

    async def _upsert_vectors_batch(
        self,
        items: list[tuple[UUID, list[float]]],
    ) -> int:
        if not items:
            return 0

        bulk_upsert = getattr(self._vector_repository, "upsert_vectors", None)
        if callable(bulk_upsert):
            try:
                await bulk_upsert(
                    candidate_ids=[candidate_id for candidate_id, _ in items],
                    embeddings=[embedding for _, embedding in items],
                )
                return 0
            except Exception as exc:
                logger.exception(
                    "candidate vector batch upsert failed, falling back to single upserts",
                    extra={
                        "batch_size": len(items),
                        "error_type": exc.__class__.__name__,
                    },
                    exc_info=exc,
                )

        failed = 0
        for candidate_id, embedding in items:
            try:
                await self._vector_repository.upsert_vector(
                    candidate_id=candidate_id,
                    embedding=embedding,
                )
            except Exception as exc:
                failed += 1
                logger.exception(
                    "candidate vector single upsert failed",
                    extra={
                        "candidate_id": str(candidate_id),
                        "error_type": exc.__class__.__name__,
                    },
                    exc_info=exc,
                )
        return failed

    async def _delete_orphaned_documents(self, active_candidate_ids: set[UUID]) -> None:
        active_ids_as_text = {str(candidate_id) for candidate_id in active_candidate_ids}

        lexical_candidate_ids = await self._lexical_repository.list_candidate_ids()
        for candidate_id in lexical_candidate_ids:
            if candidate_id in active_ids_as_text:
                continue

            await self._lexical_repository.delete_document(candidate_id=UUID(candidate_id))

        vector_candidate_ids = await self._vector_repository.list_candidate_ids()
        for candidate_id in vector_candidate_ids:
            if candidate_id in active_ids_as_text:
                continue

            await self._vector_repository.delete_vector(candidate_id=UUID(candidate_id))
