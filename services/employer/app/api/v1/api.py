from fastapi import APIRouter

from app.api.v1.endpoints import employers

api_router = APIRouter()
api_router.include_router(employers.router, prefix="/employers", tags=["employers"])
