from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from app.application.bot.constants import DEFAULT_LIST_PAGE_SIZE

PageItemT = TypeVar("PageItemT")


class PaginationUtilsMixin:
    @staticmethod
    def _extract_page_number(
        payload: dict | None,
        *,
        default: int = 1,
    ) -> int:
        if not isinstance(payload, dict):
            return default
        raw_value = payload.get("page")
        try:
            page = int(raw_value)
        except (TypeError, ValueError):
            return default
        if page < 1:
            return 1
        return page

    @staticmethod
    def _paginate_items(
        items: Sequence[PageItemT],
        *,
        page: int,
        page_size: int = DEFAULT_LIST_PAGE_SIZE,
    ) -> tuple[list[PageItemT], int, int]:
        if page_size < 1:
            page_size = DEFAULT_LIST_PAGE_SIZE
        total = len(items)
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = min(max(1, page), total_pages)
        start = (current_page - 1) * page_size
        end = start + page_size
        return list(items[start:end]), current_page, total_pages
