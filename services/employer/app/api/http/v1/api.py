from __future__ import annotations

from fastapi import APIRouter

from app.api.http.v1.routers import (
    avatars,
    contacts,
    documents,
    employers,
    health,
    internal,
    searches,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(employers.router)
api_router.include_router(avatars.router)
api_router.include_router(documents.router)
api_router.include_router(searches.router)
api_router.include_router(contacts.router)
api_router.include_router(internal.router)
