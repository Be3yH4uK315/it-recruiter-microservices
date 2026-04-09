from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.http.v1.api import api_router
from app.config import get_settings
from app.infrastructure.db.session import SessionFactory, engine
from app.infrastructure.integrations.s3_client import S3ObjectStorage
from app.infrastructure.observability.logger import configure_logging, get_logger
from app.infrastructure.observability.telemetry import (
    init_telemetry,
    instrument_app_requests,
    shutdown_telemetry,
)
from app.infrastructure.web.exception_handlers import register_exception_handlers
from app.infrastructure.web.middleware.idempotency import IdempotencyMiddleware
from app.infrastructure.web.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


async def _resolve_ngrok_public_base_url(
    *,
    app: FastAPI,
    http_client: httpx.AsyncClient,
) -> str | None:
    settings = app.state.settings

    if not settings.ngrok_api_url:
        return None

    url = f"{settings.ngrok_api_url.rstrip('/')}/api/tunnels"
    deadline = (
        asyncio.get_running_loop().time() + settings.s3_public_endpoint_discovery_timeout_seconds
    )
    poll_interval = settings.s3_public_endpoint_discovery_poll_interval_seconds
    tunnel_addr_filter = settings.ngrok_tunnel_addr_contains

    while asyncio.get_running_loop().time() < deadline:
        try:
            response = await http_client.get(url)
            response.raise_for_status()
            payload = response.json()
            tunnels = payload.get("tunnels", [])

            first_https_url: str | None = None
            first_https_addr: str | None = None

            if isinstance(tunnels, list):
                for item in tunnels:
                    if not isinstance(item, dict):
                        continue

                    public_url = item.get("public_url")
                    proto = item.get("proto")
                    tunnel_addr = (
                        item.get("config", {}).get("addr")
                        if isinstance(item.get("config"), dict)
                        else None
                    )

                    if not isinstance(public_url, str) or not public_url.startswith("https://"):
                        continue

                    if first_https_url is None:
                        first_https_url = public_url.rstrip("/")
                        first_https_addr = str(tunnel_addr) if tunnel_addr is not None else None

                    if tunnel_addr_filter:
                        if isinstance(tunnel_addr, str) and tunnel_addr_filter in tunnel_addr:
                            logger.info(
                                "ngrok public url resolved",
                                extra={
                                    "public_url": public_url,
                                    "proto": proto,
                                    "tunnel_addr": tunnel_addr,
                                },
                            )
                            return public_url.rstrip("/")
                        continue

                    logger.info(
                        "ngrok public url resolved",
                        extra={
                            "public_url": public_url,
                            "proto": proto,
                            "tunnel_addr": tunnel_addr,
                        },
                    )
                    return public_url.rstrip("/")

            if first_https_url and tunnel_addr_filter:
                logger.warning(
                    "ngrok tunnel matched by https, but filter was not found",
                    extra={
                        "ngrok_tunnel_addr_contains": tunnel_addr_filter,
                        "fallback_tunnel_addr": first_https_addr,
                        "fallback_public_url": first_https_url,
                    },
                )
                return None
        except httpx.ConnectError:
            logger.info(
                "ngrok api is not reachable yet, retrying",
                extra={"ngrok_api_url": settings.ngrok_api_url},
            )
        except Exception:
            logger.warning(
                "failed to resolve ngrok public url, retrying",
                exc_info=True,
            )

        await asyncio.sleep(poll_interval)

    logger.warning(
        "ngrok public url was not resolved in time",
        extra={
            "ngrok_api_url": settings.ngrok_api_url,
            "ngrok_tunnel_addr_contains": settings.ngrok_tunnel_addr_contains,
        },
    )
    return None


async def _configure_s3_public_endpoint(
    *,
    app: FastAPI,
    http_client: httpx.AsyncClient,
) -> bool:
    settings = app.state.settings

    if settings.s3_public_endpoint_url:
        logger.info(
            "s3 public endpoint is configured explicitly",
            extra={"s3_public_endpoint_url": settings.s3_public_endpoint_url},
        )
        return True

    ngrok_base_url = await _resolve_ngrok_public_base_url(
        app=app,
        http_client=http_client,
    )
    if not ngrok_base_url:
        logger.warning("s3 public endpoint is not resolved, retry scheduled")
        return False

    settings.s3_public_endpoint_url = ngrok_base_url
    logger.info(
        "s3 public endpoint was resolved via ngrok",
        extra={"s3_public_endpoint_url": settings.s3_public_endpoint_url},
    )
    return True


async def _configure_s3_public_endpoint_in_background(
    *,
    app: FastAPI,
    http_client: httpx.AsyncClient,
) -> None:
    settings = app.state.settings
    retry_delay = max(5.0, settings.s3_public_endpoint_discovery_poll_interval_seconds)

    while True:
        configured = await _configure_s3_public_endpoint(
            app=app,
            http_client=http_client,
        )
        if configured:
            return
        logger.info(
            "s3 public endpoint resolution will be retried in background",
            extra={"retry_delay_seconds": retry_delay},
        )
        await asyncio.sleep(retry_delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    telemetry = init_telemetry(
        service_name=settings.app_name,
        service_version=settings.app_version,
        environment=settings.app_env,
    )
    app.state.settings = settings

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
        follow_redirects=False,
        headers={
            "User-Agent": f"{settings.app_name}/{settings.app_version}",
            "Accept": "application/json",
        },
    )

    storage = S3ObjectStorage(settings)

    app.state.storage = storage
    app.state.telemetry = telemetry
    app.state.http_client = http_client

    logger.info(
        "application startup",
        extra={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.app_env,
        },
    )

    endpoint_task = None
    endpoint_task = asyncio.create_task(
        _configure_s3_public_endpoint_in_background(
            app=app,
            http_client=http_client,
        )
    )
    app.state.s3_public_endpoint_task = endpoint_task

    try:
        await storage.ensure_bucket_exists()
        yield
    finally:
        logger.info("application shutdown")
        if endpoint_task is not None:
            endpoint_task.cancel()
            with suppress(asyncio.CancelledError):
                await endpoint_task
        shutdown_telemetry(telemetry)
        await http_client.aclose()
        await engine.dispose()


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

    if settings.idempotency_enabled:
        app.add_middleware(
            IdempotencyMiddleware,
            session_factory=SessionFactory,
            header_name=settings.idempotency_header_name,
        )

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
