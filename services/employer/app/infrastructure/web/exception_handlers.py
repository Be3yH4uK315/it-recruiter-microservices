from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.domain.employer.errors import (
    ContactRequestAlreadyResolvedError,
    ContactRequestError,
    ContactRequestForbiddenError,
    ContactRequestNotFoundError,
    DuplicateDecisionError,
    EmployerAlreadyExistsError,
    EmployerDomainError,
    EmployerNotFoundError,
    InvalidEmployerFileError,
    InvalidSearchFilterError,
    SearchSessionClosedError,
    SearchSessionNotFoundError,
    SearchSessionPausedError,
)
from app.infrastructure.integrations.auth_gateway import (
    AuthGatewayError,
    AuthGatewayForbiddenError,
    AuthGatewayInvalidTokenError,
    AuthGatewayUnavailableError,
)
from app.infrastructure.integrations.file_gateway import FileGatewayError
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


async def employer_not_found_handler(
    request: Request,
    exc: EmployerNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Employer not found",
    )


async def employer_already_exists_handler(
    request: Request,
    exc: EmployerAlreadyExistsError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail="Employer already exists",
    )


async def search_session_not_found_handler(
    request: Request,
    exc: SearchSessionNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Search session not found",
    )


async def contact_request_not_found_handler(
    request: Request,
    exc: ContactRequestNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Contact request not found",
    )


async def invalid_search_filter_handler(
    request: Request,
    exc: InvalidSearchFilterError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


async def duplicate_decision_handler(
    request: Request,
    exc: DuplicateDecisionError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


async def search_session_closed_handler(
    request: Request,
    exc: SearchSessionClosedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail="Search session is closed",
    )


async def search_session_paused_handler(
    request: Request,
    exc: SearchSessionPausedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail="Search session is paused",
    )


async def contact_request_forbidden_handler(
    request: Request,
    exc: ContactRequestForbiddenError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc),
    )


async def contact_request_already_resolved_handler(
    request: Request,
    exc: ContactRequestAlreadyResolvedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


async def contact_request_error_handler(
    request: Request,
    exc: ContactRequestError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


async def auth_gateway_invalid_token_handler(
    request: Request,
    exc: AuthGatewayInvalidTokenError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid access token",
    )


async def auth_gateway_forbidden_handler(
    request: Request,
    exc: AuthGatewayForbiddenError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access forbidden",
    )


async def auth_gateway_unavailable_handler(
    request: Request,
    exc: AuthGatewayUnavailableError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Auth service is unavailable",
    )


async def auth_gateway_error_handler(
    request: Request,
    exc: AuthGatewayError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


async def file_gateway_error_handler(
    request: Request,
    exc: FileGatewayError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


async def invalid_employer_file_handler(
    request: Request,
    exc: InvalidEmployerFileError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        status_code=status.HTTP_409_CONFLICT,
        detail="Integrity constraint violation",
    )


async def stale_data_error_handler(
    request: Request,
    exc: StaleDataError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        detail="Resource was modified concurrently",
    )


async def employer_domain_error_handler(
    request: Request,
    exc: EmployerDomainError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
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
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(EmployerNotFoundError, employer_not_found_handler)
    app.add_exception_handler(EmployerAlreadyExistsError, employer_already_exists_handler)
    app.add_exception_handler(SearchSessionNotFoundError, search_session_not_found_handler)
    app.add_exception_handler(ContactRequestNotFoundError, contact_request_not_found_handler)
    app.add_exception_handler(InvalidSearchFilterError, invalid_search_filter_handler)
    app.add_exception_handler(DuplicateDecisionError, duplicate_decision_handler)
    app.add_exception_handler(SearchSessionClosedError, search_session_closed_handler)
    app.add_exception_handler(SearchSessionPausedError, search_session_paused_handler)
    app.add_exception_handler(ContactRequestForbiddenError, contact_request_forbidden_handler)
    app.add_exception_handler(
        ContactRequestAlreadyResolvedError,
        contact_request_already_resolved_handler,
    )
    app.add_exception_handler(ContactRequestError, contact_request_error_handler)
    app.add_exception_handler(AuthGatewayInvalidTokenError, auth_gateway_invalid_token_handler)
    app.add_exception_handler(AuthGatewayForbiddenError, auth_gateway_forbidden_handler)
    app.add_exception_handler(AuthGatewayUnavailableError, auth_gateway_unavailable_handler)
    app.add_exception_handler(AuthGatewayError, auth_gateway_error_handler)
    app.add_exception_handler(FileGatewayError, file_gateway_error_handler)
    app.add_exception_handler(InvalidEmployerFileError, invalid_employer_file_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(EmployerDomainError, employer_domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
