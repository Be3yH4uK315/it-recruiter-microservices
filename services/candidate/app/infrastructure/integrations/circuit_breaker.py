from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitBreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Circuit breaker is open and rejects calls."""


@dataclass(slots=True)
class AsyncCircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1

    _state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _opened_at_monotonic: float | None = field(default=None, init=False)
    _half_open_in_flight: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def configure(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: float,
        half_open_max_calls: int | None = None,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout_seconds = max(1.0, float(recovery_timeout_seconds))
        if half_open_max_calls is not None:
            self.half_open_max_calls = max(1, int(half_open_max_calls))

    def reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._opened_at_monotonic = None
        self._half_open_in_flight = 0

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            self._transition_if_needed()

            if self._state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenError("circuit breaker is open")

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_in_flight >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError("circuit breaker half-open limit reached")
                self._half_open_in_flight += 1

        try:
            result = await func()
        except Exception:
            async with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._trip_open()
                else:
                    self._failure_count += 1
                    if self._failure_count >= self.failure_threshold:
                        self._trip_open()
            raise
        else:
            async with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._reset()
                else:
                    self._failure_count = 0
            return result
        finally:
            async with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN and self._half_open_in_flight > 0:
                    self._half_open_in_flight -= 1

    def _transition_if_needed(self) -> None:
        if self._state != CircuitBreakerState.OPEN:
            return

        if self._opened_at_monotonic is None:
            return

        elapsed = time.monotonic() - self._opened_at_monotonic
        if elapsed >= self.recovery_timeout_seconds:
            self._state = CircuitBreakerState.HALF_OPEN
            self._half_open_in_flight = 0

    def _trip_open(self) -> None:
        self._state = CircuitBreakerState.OPEN
        self._opened_at_monotonic = time.monotonic()
        self._failure_count = 0
        self._half_open_in_flight = 0

    def _reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._opened_at_monotonic = None
        self._half_open_in_flight = 0


employer_gateway_circuit_breaker = AsyncCircuitBreaker()
file_gateway_circuit_breaker = AsyncCircuitBreaker()
