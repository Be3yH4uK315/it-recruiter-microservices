from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def healthcheck(request: Request) -> JSONResponse:
    settings = getattr(request.app.state, "settings", None)
    telemetry = getattr(request.app.state, "telemetry", None)
    registry = getattr(request.app.state, "resource_registry", None)

    telemetry_enabled = False
    if isinstance(telemetry, dict):
        telemetry_enabled = bool(telemetry)
    elif telemetry is not None:
        telemetry_enabled = bool(getattr(telemetry, "enabled", False))

    components: dict[str, object] = {
        "telemetry": {
            "status": "enabled" if telemetry_enabled else "disabled",
        },
        "resource_registry": {
            "status": "ok" if registry is not None else "not_initialized",
        },
    }
    ready = registry is not None

    if registry is not None and hasattr(registry, "get_health_snapshot"):
        snapshot = await registry.get_health_snapshot()
        ready = bool(snapshot.get("ready", False))
        components["resource_registry"] = {
            "status": "ok" if ready else "degraded",
        }
        extra_components = snapshot.get("components")
        if isinstance(extra_components, dict):
            components.update(extra_components)

    payload = {
        "status": "ok" if ready else "degraded",
        "service": settings.app_name if settings is not None else "search-service",
        "version": settings.app_version if settings is not None else None,
        "environment": settings.app_env if settings is not None else None,
        "components": components,
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )
