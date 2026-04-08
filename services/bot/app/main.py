from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.http.v1.api import api_router
from app.config import get_settings
from app.infrastructure.db.session import engine
from app.infrastructure.integrations.http_client import build_default_async_http_client
from app.infrastructure.observability.logger import configure_logging, get_logger
from app.infrastructure.observability.telemetry import (
    init_telemetry,
    instrument_app_requests,
    shutdown_telemetry,
)
from app.infrastructure.telegram.client import TelegramApiClient, TelegramApiError
from app.infrastructure.web.exception_handlers import register_exception_handlers
from app.infrastructure.web.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


async def _resolve_ngrok_public_base_url(
    *,
    app: FastAPI,
) -> str | None:
    settings = app.state.settings
    http_client = app.state.http_client

    if not settings.ngrok_api_url:
        return None

    url = f"{settings.ngrok_api_url.rstrip('/')}/api/tunnels"

    deadline = (
        asyncio.get_running_loop().time() + settings.telegram_webhook_discovery_timeout_seconds
    )
    poll_interval = settings.telegram_webhook_discovery_poll_interval_seconds

    while asyncio.get_running_loop().time() < deadline:
        try:
            response = await http_client.get(url)
            response.raise_for_status()
            payload = response.json()
            tunnels = payload.get("tunnels", [])

            if isinstance(tunnels, list):
                for item in tunnels:
                    if not isinstance(item, dict):
                        continue

                    public_url = item.get("public_url")
                    proto = item.get("proto")

                    if isinstance(public_url, str) and public_url.startswith("https://"):
                        logger.info(
                            "ngrok public url resolved",
                            extra={
                                "public_url": public_url,
                                "proto": proto,
                            },
                        )
                        return public_url.rstrip("/")
        except Exception:
            logger.warning(
                "failed to resolve ngrok public url, retrying",
                exc_info=True,
            )

        await asyncio.sleep(poll_interval)

    logger.warning(
        "ngrok public url was not resolved in time",
        extra={"ngrok_api_url": settings.ngrok_api_url},
    )
    return None


async def _resolve_telegram_webhook_url(
    *,
    app: FastAPI,
) -> str | None:
    settings = app.state.settings

    if settings.telegram_webhook_url:
        return settings.telegram_webhook_url.rstrip("/")

    ngrok_base_url = await _resolve_ngrok_public_base_url(app=app)
    if ngrok_base_url:
        return f"{ngrok_base_url}{settings.telegram_webhook_path}"

    return None


async def _configure_telegram_webhook(
    *,
    app: FastAPI,
) -> None:
    settings = app.state.settings
    http_client = app.state.http_client

    if not settings.telegram_bot_token:
        logger.warning("telegram bot token is not configured, webhook setup skipped")
        return

    telegram_client = TelegramApiClient(
        client=http_client,
        base_url=settings.telegram_api_base_url,
        bot_token=settings.telegram_bot_token,
    )

    try:
        me = await telegram_client.get_me()
        logger.info(
            "telegram bot identity resolved",
            extra={
                "telegram_bot_id": me.get("id"),
                "telegram_bot_username": me.get("username"),
            },
        )
    except TelegramApiError as exc:
        logger.warning("telegram getMe failed", exc_info=exc)
        return

    if settings.telegram_mode != "webhook":
        logger.info(
            "telegram webhook setup skipped because mode is not webhook",
            extra={"telegram_mode": settings.telegram_mode},
        )
        return

    webhook_url = await _resolve_telegram_webhook_url(app=app)
    if not webhook_url:
        logger.warning("telegram webhook url is not resolved, webhook setup skipped")
        return

    try:
        result = await telegram_client.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret_token,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False,
        )
        logger.info(
            "telegram webhook configured",
            extra={
                "webhook_url": webhook_url,
                "has_custom_certificate": result.get("has_custom_certificate"),
                "pending_update_count": result.get("pending_update_count"),
            },
        )

        webhook_info = await telegram_client.get_webhook_info()
        logger.info(
            "telegram webhook info fetched",
            extra={
                "url": webhook_info.get("url"),
                "has_custom_certificate": webhook_info.get("has_custom_certificate"),
                "pending_update_count": webhook_info.get("pending_update_count"),
                "last_error_date": webhook_info.get("last_error_date"),
                "last_error_message": webhook_info.get("last_error_message"),
                "max_connections": webhook_info.get("max_connections"),
            },
        )
    except TelegramApiError as exc:
        logger.warning("telegram webhook setup failed", exc_info=exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    telemetry = init_telemetry(
        service_name=settings.app_name,
        service_version=settings.app_version,
        environment=settings.app_env,
    )
    http_client = build_default_async_http_client(settings)

    app.state.http_client = http_client
    app.state.settings = settings
    app.state.telemetry = telemetry

    logger.info(
        "application startup",
        extra={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.app_env,
            "telegram_mode": settings.telegram_mode,
            "metrics_enabled": settings.metrics_enabled,
            "swagger_enabled": settings.swagger_enabled,
        },
    )

    await _configure_telegram_webhook(app=app)

    try:
        yield
    finally:
        logger.info("application shutdown")
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
