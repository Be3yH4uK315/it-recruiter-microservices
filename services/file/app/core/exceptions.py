from typing import Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Универсальный обработчик ошибок.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "An unexpected error occurred."
    details = None

    if hasattr(exc, "status_code"):
        status_code = exc.status_code
        message = getattr(exc, "detail", str(exc))
        code = f"http_{status_code}"
    
    logger.error(
        "request_failed",
        error=str(exc),
        status_code=status_code,
        url=str(request.url),
        method=request.method
    )

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=code,
            message=message,
            details=details
        ).model_dump(mode="json")
    )