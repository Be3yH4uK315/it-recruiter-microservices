import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import search
from app.core.logger import setup_logging
from app.core.resources import resources
from app.core.telemetry import setup_telemetry
from app.services.consumer import consumer
from app.services.milvus_client import milvus_client

setup_logging()
logger = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Search Service startup...")
    await resources.startup()
    milvus_client.connect()
    consumer_task = asyncio.create_task(consumer.connect_and_consume())
    yield
    logger.info("Search Service shutdown...")
    consumer_task.cancel()
    milvus_client.disconnect()
    await resources.shutdown()


app = FastAPI(title="Search & Matching Service", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

setup_telemetry(app, "search_service")
Instrumentator().instrument(app).expose(app)

app.include_router(search.router, prefix="/v1/search", tags=["Search"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "search-service"}
