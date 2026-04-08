from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True, frozen=True)
class RateLimitResult:
    allowed: bool
    reason: str | None = None


class RateLimitService:
    def __init__(
        self,
        *,
        enabled: bool,
        messages_per_second: float,
        callbacks_burst: int,
        callbacks_cooldown_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._messages_per_second = messages_per_second
        self._callbacks_burst = callbacks_burst
        self._callbacks_cooldown_seconds = callbacks_cooldown_seconds

        self._message_hits: dict[int, deque[float]] = defaultdict(deque)
        self._callback_hits: dict[int, deque[float]] = defaultdict(deque)
        self._callback_blocked_until: dict[int, float] = {}

    def check_message(self, *, telegram_user_id: int) -> RateLimitResult:
        if not self._enabled:
            return RateLimitResult(allowed=True)

        now = monotonic()
        window_seconds = 1.0
        hits = self._message_hits[telegram_user_id]
        self._trim(hits, now=now, window_seconds=window_seconds)

        max_hits = max(1, int(self._messages_per_second * window_seconds))
        if len(hits) >= max_hits:
            return RateLimitResult(allowed=False, reason="message_rate_limited")

        hits.append(now)
        return RateLimitResult(allowed=True)

    def check_callback(self, *, telegram_user_id: int) -> RateLimitResult:
        if not self._enabled:
            return RateLimitResult(allowed=True)

        now = monotonic()
        blocked_until = self._callback_blocked_until.get(telegram_user_id)
        if blocked_until is not None and now < blocked_until:
            return RateLimitResult(allowed=False, reason="callback_cooldown")

        hits = self._callback_hits[telegram_user_id]
        self._trim(hits, now=now, window_seconds=1.0)
        if len(hits) >= self._callbacks_burst:
            self._callback_blocked_until[telegram_user_id] = now + self._callbacks_cooldown_seconds
            hits.clear()
            return RateLimitResult(allowed=False, reason="callback_rate_limited")

        hits.append(now)
        return RateLimitResult(allowed=True)

    @staticmethod
    def _trim(hits: deque[float], *, now: float, window_seconds: float) -> None:
        boundary = now - window_seconds
        while hits and hits[0] <= boundary:
            hits.popleft()
