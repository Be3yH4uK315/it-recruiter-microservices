from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _json_response(
    *,
    request: Request,
    status_code: int,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "detail": detail,
        "request_id": _request_id(request),
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    logger.exception("integrity error", extra={"request_id": _request_id(request)}, exc_info=exc)
    return _json_response(
        request=request,
        status_code=409,
        detail="Integrity constraint violation",
    )


async def stale_data_error_handler(
    request: Request,
    exc: StaleDataError,
) -> JSONResponse:
    logger.warning("stale data error", extra={"request_id": _request_id(request)}, exc_info=exc)
    return _json_response(
        request=request,
        status_code=409,
        detail="Resource was modified concurrently",
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "unhandled exception", extra={"request_id": _request_id(request)}, exc_info=exc
    )
    return _json_response(
        request=request,
        status_code=500,
        detail="Internal server error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
