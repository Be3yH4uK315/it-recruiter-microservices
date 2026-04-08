from __future__ import annotations

from collections.abc import Callable

from app.application.candidates.queries.get_candidate_search_document import (
    CandidateSearchDocumentView,
)
from app.application.common.ttl_cache import TtlCache
from app.application.common.uow import UnitOfWork
from app.domain.candidate.enums import CandidateStatus

_SEARCH_DOCUMENT_LIST_CACHE = TtlCache[tuple[int, int], list[CandidateSearchDocumentView]]()


def clear_candidate_search_document_list_cache() -> None:
    _SEARCH_DOCUMENT_LIST_CACHE.clear()


class ListCandidateSearchDocumentsHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        cache_ttl_seconds: float = 0.0,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache_ttl_seconds = cache_ttl_seconds

    async def __call__(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CandidateSearchDocumentView]:
        cache_key = (limit, offset)
        cached = _SEARCH_DOCUMENT_LIST_CACHE.get(cache_key)
        if cached is not None:
            return cached

        async with self._uow_factory() as uow:
            candidates = await uow.candidates.list_for_search(limit=limit, offset=offset)
            result = [
                CandidateSearchDocumentView.from_candidate(item)
                for item in candidates
                if item.status == CandidateStatus.ACTIVE
            ]

        _SEARCH_DOCUMENT_LIST_CACHE.set(
            cache_key,
            result,
            ttl_seconds=self._cache_ttl_seconds,
        )
        return result
