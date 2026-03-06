from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.api import api_router
from app.core.logger import setup_logging
from app.core.resources import resources
from app.core.telemetry import setup_telemetry

setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Employer Service startup...")
    await resources.startup()
    yield
    logger.info("Employer Service shutdown...")
    await resources.shutdown()


app = FastAPI(title="Employer Service", lifespan=lifespan)

setup_telemetry(app, "employer_service")
Instrumentator().instrument(app).expose(app)

app.include_router(api_router, prefix="/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
