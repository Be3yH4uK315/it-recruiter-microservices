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
from app.application.common.exceptions import (
    IntegrationUnavailableError as ApplicationIntegrationUnavailableError,
)
from app.domain.candidate.errors import (
    AvatarNotFoundError,
    CandidateAlreadyExistsError,
    CandidateBlockedError,
    CandidateDomainError,
    CandidateNotFoundError,
    CannotUnblockYourselfError,
    IntegrationUnavailableError,
    InvalidCandidateFileError,
    InvalidSalaryRangeError,
    ResumeNotFoundError,
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


async def candidate_not_found_handler(
    request: Request,
    exc: CandidateNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="Candidate not found",
    )


async def candidate_already_exists_handler(
    request: Request,
    exc: CandidateAlreadyExistsError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=409,
        detail="Candidate already exists",
    )


async def candidate_blocked_handler(
    request: Request,
    exc: CandidateBlockedError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=403,
        detail="Candidate is blocked",
    )


async def cannot_unblock_yourself_handler(
    request: Request,
    exc: CannotUnblockYourselfError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=403,
        detail="Cannot unblock yourself",
    )


async def resume_not_found_handler(
    request: Request,
    exc: ResumeNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="Resume not found",
    )


async def avatar_not_found_handler(
    request: Request,
    exc: AvatarNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail="Avatar not found",
    )


async def invalid_salary_range_handler(
    request: Request,
    exc: InvalidSalaryRangeError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=422,
        detail=str(exc),
    )


async def invalid_candidate_file_handler(
    request: Request,
    exc: InvalidCandidateFileError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=422,
        detail=str(exc),
    )


async def integration_unavailable_handler(
    request: Request,
    exc: IntegrationUnavailableError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
        detail=str(exc),
    )


async def app_integration_unavailable_handler(
    request: Request,
    exc: ApplicationIntegrationUnavailableError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
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


async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=400,
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


async def candidate_domain_error_handler(
    request: Request,
    exc: CandidateDomainError,
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
    app.add_exception_handler(CandidateNotFoundError, candidate_not_found_handler)
    app.add_exception_handler(CandidateAlreadyExistsError, candidate_already_exists_handler)
    app.add_exception_handler(CandidateBlockedError, candidate_blocked_handler)
    app.add_exception_handler(CannotUnblockYourselfError, cannot_unblock_yourself_handler)
    app.add_exception_handler(ResumeNotFoundError, resume_not_found_handler)
    app.add_exception_handler(AvatarNotFoundError, avatar_not_found_handler)
    app.add_exception_handler(InvalidSalaryRangeError, invalid_salary_range_handler)
    app.add_exception_handler(InvalidCandidateFileError, invalid_candidate_file_handler)
    app.add_exception_handler(IntegrationUnavailableError, integration_unavailable_handler)
    app.add_exception_handler(
        ApplicationIntegrationUnavailableError,
        app_integration_unavailable_handler,
    )
    app.add_exception_handler(ValidationApplicationError, validation_application_error_handler)
    app.add_exception_handler(AccessDeniedError, access_denied_error_handler)
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(CandidateDomainError, candidate_domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
