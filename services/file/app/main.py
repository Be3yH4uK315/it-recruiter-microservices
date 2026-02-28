from fastapi import FastAPI
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.api.v1 import files
from app.core.telemetry import setup_telemetry
from app.services.s3_client import s3_service
from app.core.logger import setup_logging

setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("File Service startup...")
    try:
        await s3_service.ensure_bucket_exists()
    except Exception as e:
        logger.critical(f"Failed to initialize S3 bucket: {e}")
    yield
    logger.info("File Service shutdown...")

app = FastAPI(title="File Service", lifespan=lifespan)

setup_telemetry(app, "file_service")
Instrumentator().instrument(app).expose(app)

app.include_router(files.router, prefix="/v1/files", tags=["Files"])

@app.get("/health")
def health_check():
    return {"status": "ok"}