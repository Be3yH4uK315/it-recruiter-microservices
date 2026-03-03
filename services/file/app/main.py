from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.api.v1 import files
from app.core.telemetry import setup_telemetry
from app.services.s3_client import s3_service
from app.core.logger import setup_logging
from app.core.db import get_db
from app.core.exceptions import global_exception_handler

setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("File Service startup...")
    try:
        await s3_service.ensure_bucket_exists()
    except Exception as e:
        logger.critical(f"Failed to initialize S3 bucket: {e}")
        raise
    yield
    logger.info("File Service shutdown...")


app = FastAPI(title="File Service", lifespan=lifespan)

setup_telemetry(app, "file_service")
Instrumentator().instrument(app).expose(app)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, global_exception_handler)
app.add_exception_handler(RequestValidationError, global_exception_handler)

app.include_router(files.router, prefix="/v1/files", tags=["Files"])


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe with dependency checks."""
    health_status = {
        "status": "ok",
        "service": "file-service",
        "components": {},
    }
    has_error = False

    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["db"] = "up"
    except Exception as e:
        health_status["components"]["db"] = f"down: {str(e)}"
        has_error = True

    try:
        await s3_service.ensure_bucket_exists()
        s3_stats = s3_service.get_stats()
        health_status["components"]["s3"] = {
            "status": "up",
            "uploads": s3_stats["upload_count"],
            "errors": s3_stats["upload_errors"],
        }
    except Exception as e:
        health_status["components"]["s3"] = f"down: {str(e)}"
        has_error = True

    if has_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_status
        )

    return health_status


@app.get("/health/s3", tags=["Health"])
async def s3_health_check():
    """S3 specific health check."""
    try:
        await s3_service.ensure_bucket_exists()
        stats = s3_service.get_stats()
        return {
            "status": "up",
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"S3 connection failed: {str(e)}",
        )
