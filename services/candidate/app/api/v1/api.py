from fastapi import APIRouter
from app.api.v1.endpoints import (
    candidates,
    avatars,
    resumes
)

api_router = APIRouter()

api_router.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
api_router.include_router(avatars.router, prefix="/candidates", tags=["Avatars"])
api_router.include_router(resumes.router, prefix="/candidates", tags=["Resumes"])
