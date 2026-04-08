from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.http.v1.dependencies import (
    get_settings_dependency,
    get_update_router_service,
)
from app.application.bot.services.update_router import UpdateRouterService
from app.config import Settings
from app.infrastructure.observability.logger import get_logger
from app.infrastructure.telegram.client import TelegramApiError
from app.schemas.telegram import TelegramUpdate

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = get_logger(__name__)


def _verify_webhook_secret(
    *,
    settings: Settings,
    secret_header: str | None,
) -> None:
    expected = settings.telegram_webhook_secret_token
    if not expected:
        return
    if secret_header != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid telegram webhook secret token",
        )


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    update: TelegramUpdate,
    router_service: UpdateRouterService = Depends(get_update_router_service),
    settings: Settings = Depends(get_settings_dependency),
    telegram_secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict:
    _verify_webhook_secret(
        settings=settings,
        secret_header=telegram_secret_token,
    )

    try:
        result = await router_service.route(update)
    except TelegramApiError as exc:
        if not settings.allows_degraded_telegram_webhook_ack:
            raise

        logger.warning(
            "telegram webhook acknowledged in degraded mode because placeholder bot token is configured",
            extra={
                "update_id": update.update_id,
                "environment": settings.app_env,
            },
            exc_info=exc,
        )
        result = {
            "status": "degraded",
            "reason": "telegram_api_unavailable",
            "update_id": update.update_id,
        }

    return {
        "ok": True,
        "result": result,
        "request_id": getattr(request.state, "request_id", None),
    }
