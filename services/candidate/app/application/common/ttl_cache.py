from __future__ import annotations

from collections import OrderedDict
from time import monotonic
from typing import Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class TtlCache(Generic[K, V]):
    def __init__(self, *, max_entries: int = 512) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if expires_at <= monotonic():
            self._entries.pop(key, None)
            return None

        self._entries.move_to_end(key)
        return value

    def set(self, key: K, value: V, *, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return

        self._entries[key] = (monotonic() + ttl_seconds, value)
        self._entries.move_to_end(key)
        self._prune()

    def clear(self) -> None:
        self._entries.clear()

    def _prune(self) -> None:
        now = monotonic()
        expired_keys = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)

        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
