from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.application.common.exceptions import (
    AccessDeniedError,
    ApplicationError,
    ValidationApplicationError,
)
from app.domain.file.errors import (
    FileAlreadyDeletedError,
    FileDomainError,
    FileNotFoundError,
    InvalidFileStateError,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _json_response(
    *,
    request: Request,
    status_code: int,
    detail: str,
    extra: dict | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "detail": detail,
        "request_id": _request_id(request),
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


async def file_not_found_handler(
    request: Request,
    exc: FileNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="File not found",
    )


async def file_already_deleted_handler(
    request: Request,
    exc: FileAlreadyDeletedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=409,
        detail=str(exc),
    )


async def invalid_file_state_handler(
    request: Request,
    exc: InvalidFileStateError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=409,
        detail=str(exc),
    )


async def validation_application_error_handler(
    request: Request,
    exc: ValidationApplicationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=422,
        detail=str(exc),
    )


async def access_denied_error_handler(
    request: Request,
    exc: AccessDeniedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=403,
        detail=str(exc),
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    logger.exception(
        "integrity error",
        extra={"request_id": _request_id(request)},
        exc_info=exc,
    )
    return _json_response(
        request=request,
        status_code=409,
        detail="Integrity constraint violation",
    )


async def stale_data_error_handler(
    request: Request,
    exc: StaleDataError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=409,
        detail="Resource was modified concurrently",
    )


async def file_domain_error_handler(
    request: Request,
    exc: FileDomainError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=400,
        detail=str(exc),
    )


async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=400,
        detail=str(exc),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "unhandled exception",
        extra={"request_id": _request_id(request)},
        exc_info=exc,
    )
    return _json_response(
        request=request,
        status_code=500,
        detail="Internal server error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(FileNotFoundError, file_not_found_handler)
    app.add_exception_handler(FileAlreadyDeletedError, file_already_deleted_handler)
    app.add_exception_handler(InvalidFileStateError, invalid_file_state_handler)
    app.add_exception_handler(ValidationApplicationError, validation_application_error_handler)
    app.add_exception_handler(AccessDeniedError, access_denied_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(FileDomainError, file_domain_error_handler)
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
