from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.endpoints import auth
from app.core.logger import setup_logging
from app.core.telemetry import setup_telemetry

setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth Service startup...")
    yield
    logger.info("Auth Service shutdown...")


app = FastAPI(title="Auth Service", lifespan=lifespan)

setup_telemetry(app, "auth_service")
Instrumentator().instrument(app).expose(app)

app.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
