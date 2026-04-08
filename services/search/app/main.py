from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.http.v1.api import api_router
from app.config import get_settings
from app.infrastructure.integrations.http_client import build_default_async_http_client
from app.infrastructure.integrations.resource_registry import ResourceRegistry
from app.infrastructure.observability.logger import configure_logging, get_logger
from app.infrastructure.observability.telemetry import (
    init_telemetry,
    instrument_app_requests,
    shutdown_telemetry,
)
from app.infrastructure.web.exception_handlers import register_exception_handlers
from app.infrastructure.web.middleware.request_id import RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    logger = get_logger(__name__)
    telemetry = init_telemetry(
        service_name=settings.app_name,
        service_version=settings.app_version,
        environment=settings.app_env,
    )

    http_client = build_default_async_http_client(settings)
    resource_registry = ResourceRegistry(
        settings=settings,
        http_client=http_client,
    )

    try:
        await resource_registry.startup()

        app.state.http_client = http_client
        app.state.settings = settings
        app.state.telemetry = telemetry
        app.state.resource_registry = resource_registry

        logger.info(
            "application startup",
            extra={
                "app_name": settings.app_name,
                "app_version": settings.app_version,
                "environment": settings.app_env,
            },
        )

        yield
    finally:
        logger.info("application shutdown")
        shutdown_telemetry(telemetry)
        await resource_registry.shutdown()
        await http_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=settings.docs_url if settings.swagger_enabled else None,
        redoc_url=settings.redoc_url if settings.swagger_enabled else None,
        openapi_url=settings.openapi_url if settings.swagger_enabled else None,
    )

    instrument_app_requests(app, service_name=settings.app_name)

    app.add_middleware(RequestIdMiddleware, settings=settings)

    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    app.include_router(api_router)
    register_exception_handlers(app)

    if settings.metrics_enabled:
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            should_instrument_requests_inprogress=True,
            excluded_handlers=[
                "/metrics",
                "/api/v1/health",
                "/docs",
                "/redoc",
                "/openapi.json",
            ],
        ).instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
            should_gzip=True,
        )

    return app


app = create_app()
