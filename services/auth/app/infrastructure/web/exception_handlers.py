from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.domain.auth.errors import (
    AuthDomainError,
    InvalidAccessTokenError,
    InvalidRefreshTokenError,
    InvalidTelegramAuthError,
    RefreshSessionNotFoundError,
    RefreshSessionRevokedError,
    UserAlreadyExistsError,
    UserInactiveError,
    UserNotFoundError,
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
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "detail": detail,
        "request_id": _request_id(request),
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


async def user_not_found_handler(
    request: Request,
    exc: UserNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="User not found",
    )


async def user_already_exists_handler(
    request: Request,
    exc: UserAlreadyExistsError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=409,
        detail="User already exists",
    )


async def invalid_telegram_auth_handler(
    request: Request,
    exc: InvalidTelegramAuthError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=401,
        detail=str(exc),
    )


async def invalid_refresh_token_handler(
    request: Request,
    exc: InvalidRefreshTokenError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=401,
        detail=str(exc),
    )


async def invalid_access_token_handler(
    request: Request,
    exc: InvalidAccessTokenError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=401,
        detail=str(exc),
    )


async def refresh_session_not_found_handler(
    request: Request,
    exc: RefreshSessionNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="Refresh session not found",
    )


async def refresh_session_revoked_handler(
    request: Request,
    exc: RefreshSessionRevokedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=401,
        detail=str(exc),
    )


async def user_inactive_handler(
    request: Request,
    exc: UserInactiveError,
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
    logger.warning(
        "stale data error",
        extra={"request_id": _request_id(request)},
        exc_info=exc,
    )
    return _json_response(
        request=request,
        status_code=409,
        detail="Resource was modified concurrently",
    )


async def auth_domain_error_handler(
    request: Request,
    exc: AuthDomainError,
) -> JSONResponse:
    logger.warning(
        "auth domain error",
        extra={
            "request_id": _request_id(request),
            "error_type": exc.__class__.__name__,
        },
    )
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
    app.add_exception_handler(UserNotFoundError, user_not_found_handler)
    app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
    app.add_exception_handler(InvalidTelegramAuthError, invalid_telegram_auth_handler)
    app.add_exception_handler(InvalidRefreshTokenError, invalid_refresh_token_handler)
    app.add_exception_handler(InvalidAccessTokenError, invalid_access_token_handler)
    app.add_exception_handler(RefreshSessionNotFoundError, refresh_session_not_found_handler)
    app.add_exception_handler(RefreshSessionRevokedError, refresh_session_revoked_handler)
    app.add_exception_handler(UserInactiveError, user_inactive_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(AuthDomainError, auth_domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
