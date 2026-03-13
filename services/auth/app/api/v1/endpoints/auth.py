from app.core.config import settings
from app.core.db import get_db
from app.schemas.auth import (
    BotLoginRequest,
    LogoutRequest,
    RefreshRequest,
    TelegramLoginData,
    TokenResponse,
)
from app.services.service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status
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
    Позволяет динамически менять роль (CANDIDATE/EMPLOYER).
    """
    if request.bot_secret != settings.INTERNAL_BOT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid bot secret")

    return await service.authenticate_via_trusted_bot(
        telegram_id=request.telegram_id, username=request.username, role=request.role
    )


@router.post("/login/telegram", response_model=TokenResponse)
async def login_telegram(
    login_data: TelegramLoginData, service: AuthService = Depends(get_auth_service)
):
    """Обмен данных от Telegram на JWT токены."""
    return await service.authenticate_telegram(login_data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    """Получение новой пары токенов по Refresh Token."""
    return await service.refresh_access_token(request.refresh_token)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: LogoutRequest, service: AuthService = Depends(get_auth_service)):
    """Выход с текущего устройства (инвалидация конкретного рефреш токена)."""
    await service.logout(request.refresh_token)
    return {"status": "success", "detail": "Logged out successfully"}


@router.post("/logout/all", status_code=status.HTTP_200_OK)
async def logout_all(request: LogoutRequest, service: AuthService = Depends(get_auth_service)):
    """Выход со всех устройств (инвалидация всех сессий пользователя)."""
    await service.logout_all(request.refresh_token)
    return {"status": "success", "detail": "Logged out from all devices"}
