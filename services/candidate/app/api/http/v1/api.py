from __future__ import annotations

from fastapi import APIRouter

from app.api.http.v1.routers import avatars, candidates, health, internal, resumes

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(candidates.router)
api_router.include_router(avatars.router)
api_router.include_router(resumes.router)
api_router.include_router(internal.router)
