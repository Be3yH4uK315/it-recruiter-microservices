from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.integrations.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)


@pytest.mark.asyncio
async def test_circuit_breaker_success_keeps_closed() -> None:
    breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.01)

    async def ok() -> str:
        return "ok"

    result = await breaker.call(ok)

    assert result == "ok"
    assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures() -> None:
    breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.01)

    async def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state == CircuitBreakerState.CLOSED

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state == CircuitBreakerState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(fail)


@pytest.mark.asyncio
async def test_circuit_breaker_moves_to_half_open_and_closes_on_success() -> None:
    breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.01)

    async def fail() -> None:
        raise RuntimeError("boom")

    async def ok() -> str:
        return "ok"

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state == CircuitBreakerState.OPEN

    await asyncio.sleep(0.02)

    result = await breaker.call(ok)

    assert result == "ok"
    assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_reopens_when_half_open_call_fails() -> None:
    breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.01)

    async def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state == CircuitBreakerState.OPEN

    await asyncio.sleep(0.02)

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state == CircuitBreakerState.OPEN
