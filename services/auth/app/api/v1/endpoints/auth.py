from app.core.config import settings
from app.core.db import get_db
from app.schemas.auth import (
    BotLoginRequest,
    RefreshRequest,
    TelegramLoginData,
    TokenResponse,
)
from app.services.service import AuthService
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login/bot", response_model=TokenResponse)
async def login_bot_internal(
    request: BotLoginRequest, service: AuthService = Depends(get_auth_service)
):
    """
    Эндпоинт только для Bot Service.
    """
    if request.bot_secret != settings.INTERNAL_BOT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid bot secret")

    return await service.authenticate_via_trusted_bot(request.telegram_id, request.username)


@router.post("/login/telegram", response_model=TokenResponse)
async def login_telegram(
    login_data: TelegramLoginData, service: AuthService = Depends(get_auth_service)
):
    """
    Обмен данных от Telegram на JWT токены.
    """
    return await service.authenticate_telegram(login_data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    """
    Получение новой пары токенов по Refresh Token.
    """
    return await service.refresh_access_token(request.refresh_token)
