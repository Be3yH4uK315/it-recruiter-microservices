from __future__ import annotations

from fastapi import APIRouter

from app.api.http.v1.routers.health import router as health_router
from app.api.http.v1.routers.internal import router as internal_router
from app.api.http.v1.routers.telegram_webhook import router as telegram_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(telegram_router)
api_router.include_router(internal_router)
