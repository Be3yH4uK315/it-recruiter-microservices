from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.common.exceptions import (
    ApplicationError,
    IntegrationApplicationError,
    ValidationApplicationError,
)
from app.domain.search.errors import (
    CandidateDocumentNotFoundError,
    EmbeddingGenerationError,
    InvalidSearchFilterError,
    RankingUnavailableError,
    SearchBackendUnavailableError,
    SearchDomainError,
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


async def validation_application_error_handler(
    request: Request,
    exc: ValidationApplicationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=422,
        detail=str(exc),
    )


async def integration_application_error_handler(
    request: Request,
    exc: IntegrationApplicationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
        detail=str(exc),
    )


async def invalid_search_filter_error_handler(
    request: Request,
    exc: InvalidSearchFilterError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=422,
        detail=str(exc),
    )


async def candidate_document_not_found_error_handler(
    request: Request,
    exc: CandidateDocumentNotFoundError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=404,
        detail=str(exc),
    )


async def search_backend_unavailable_error_handler(
    request: Request,
    exc: SearchBackendUnavailableError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
        detail=str(exc),
    )


async def embedding_generation_error_handler(
    request: Request,
    exc: EmbeddingGenerationError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
        detail=str(exc),
    )


async def ranking_unavailable_error_handler(
    request: Request,
    exc: RankingUnavailableError,
) -> JSONResponse:
    return _json_response(
        request=request,
        status_code=503,
        detail=str(exc),
    )


async def search_domain_error_handler(
    request: Request,
    exc: SearchDomainError,
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
    app.add_exception_handler(
        ValidationApplicationError,
        validation_application_error_handler,
    )
    app.add_exception_handler(
        IntegrationApplicationError,
        integration_application_error_handler,
    )
    app.add_exception_handler(
        InvalidSearchFilterError,
        invalid_search_filter_error_handler,
    )
    app.add_exception_handler(
        CandidateDocumentNotFoundError,
        candidate_document_not_found_error_handler,
    )
    app.add_exception_handler(
        SearchBackendUnavailableError,
        search_backend_unavailable_error_handler,
    )
    app.add_exception_handler(
        EmbeddingGenerationError,
        embedding_generation_error_handler,
    )
    app.add_exception_handler(
        RankingUnavailableError,
        ranking_unavailable_error_handler,
    )
    app.add_exception_handler(
        SearchDomainError,
        search_domain_error_handler,
    )
    app.add_exception_handler(
        ApplicationError,
        application_error_handler,
    )
    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )
