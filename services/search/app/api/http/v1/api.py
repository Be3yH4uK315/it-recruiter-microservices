from __future__ import annotations

from fastapi import APIRouter

from app.api.http.v1.routers import health, internal, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(search.router)
api_router.include_router(internal.router)
