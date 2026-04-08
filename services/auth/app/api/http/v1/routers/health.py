from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def healthcheck(request: Request) -> dict[str, object]:
    settings = getattr(request.app.state, "settings", None)
    telemetry = getattr(request.app.state, "telemetry", None)

    return {
        "status": "ok",
        "service": settings.app_name if settings is not None else "auth-service",
        "version": settings.app_version if settings is not None else None,
        "environment": settings.app_env if settings is not None else None,
        "components": {
            "telemetry": {
                "status": "enabled" if getattr(telemetry, "enabled", False) else "disabled",
            },
        },
    }
