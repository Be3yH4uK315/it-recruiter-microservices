from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import structlog
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.api import api_router
from app.core.middleware import RequestIDMiddleware
from app.core.idempotency import IdempotencyMiddleware
from app.core.exceptions import global_exception_handler
from app.core.telemetry import setup_telemetry
from app.services.publisher import publisher
from app.core.resources import resources
from app.core.logger import setup_logging
from app.core.db import get_db
from app.core.config import settings

setup_logging()
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Candidate Service startup...")
    await resources.startup()
    await publisher.connect()
    yield
    logger.info("Candidate Service shutdown...")
    await publisher.close()
    await resources.shutdown()

app = FastAPI(title="Candidate Service", lifespan=lifespan)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestIDMiddleware)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, global_exception_handler)
app.add_exception_handler(RequestValidationError, global_exception_handler)

setup_telemetry(app, "candidate_service")
Instrumentator().instrument(app).expose(app)

app.include_router(api_router, prefix="/v1")

@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Liveness probe.
    """
    health_status = {"status": "ok", "components": {}}
    has_error = False
    
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["db"] = "up"
    except Exception as e:
        health_status["components"]["db"] = f"down: {str(e)}"
        has_error = True
        
    if publisher.connection and not publisher.connection.is_closed:
        health_status["components"]["rabbitmq"] = "up"
    else:
        health_status["components"]["rabbitmq"] = "down"
        has_error = True

    if has_error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_status)
        
    return health_status