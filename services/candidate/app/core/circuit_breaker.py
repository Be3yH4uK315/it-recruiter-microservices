import time
from typing import Callable, Any
import structlog

from app.core.config import settings

logger = structlog.get_logger()

class CircuitBreakerOpenException(Exception):
    pass

class SimpleCircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_timeout: int):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit Breaker trying to recover (HALF-OPEN)...")
                self.state = "CLOSED"
            else:
                raise CircuitBreakerOpenException("Circuit is open")

        try:
            result = await func(*args, **kwargs)
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(
                    f"Circuit Breaker OPENED after {self.failure_count} failures.", 
                    threshold=self.failure_threshold
                )
            raise e

employer_service_breaker = SimpleCircuitBreaker(
    failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
)