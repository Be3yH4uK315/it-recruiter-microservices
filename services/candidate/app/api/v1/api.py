from app.api.v1.endpoints import avatars, candidates, resumes
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(candidates.router, prefix="/candidates", tags=["Candidates"])
api_router.include_router(avatars.router, prefix="/candidates", tags=["Avatars"])
api_router.include_router(resumes.router, prefix="/candidates", tags=["Resumes"])
