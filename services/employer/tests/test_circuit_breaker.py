import pytest
import time
from unittest.mock import AsyncMock
from app.core.circuit_breaker import SimpleCircuitBreaker, CircuitBreakerOpenException

@pytest.mark.asyncio
async def test_circuit_breaker_success():
    """Тест нормальной работы (CLOSED)."""
    cb = SimpleCircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    func = AsyncMock(return_value="success")
    res = await cb.call(func)
    
    assert res == "success"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Тест перехода в OPEN после ошибок."""
    cb = SimpleCircuitBreaker(failure_threshold=2, recovery_timeout=1)
    func = AsyncMock(side_effect=ValueError("Boom"))
    
    with pytest.raises(ValueError):
        await cb.call(func)
    assert cb.failure_count == 1
    assert cb.state == "CLOSED"
    
    with pytest.raises(ValueError):
        await cb.call(func)
    assert cb.failure_count == 2
    assert cb.state == "OPEN"
    
    with pytest.raises(CircuitBreakerOpenException):
        await cb.call(func)

@pytest.mark.asyncio
async def test_circuit_breaker_recovery(mocker):
    """Тест восстановления (HALF-OPEN -> CLOSED)."""
    cb = SimpleCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    cb.state = "OPEN"
    cb.last_failure_time = time.time() - 0.2
    
    func = AsyncMock(return_value="recovered")
    
    res = await cb.call(func)
    
    assert res == "recovered"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0
