from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def healthcheck(request: Request) -> dict:
    settings = getattr(request.app.state, "settings", None)
    telemetry = getattr(request.app.state, "telemetry", None)
    http_client = getattr(request.app.state, "http_client", None)

    return {
        "status": "ok",
        "service": settings.app_name if settings is not None else "candidate-service",
        "version": settings.app_version if settings is not None else None,
        "environment": settings.app_env if settings is not None else None,
        "components": {
            "http_client": {
                "status": "ok" if http_client is not None else "not_initialized",
            },
            "telemetry": {
                "status": "enabled" if getattr(telemetry, "enabled", False) else "disabled",
            },
        },
    }
