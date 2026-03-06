import hashlib
from datetime import datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config, security
from app.models.auth import RefreshToken, User, UserRole
from app.schemas.auth import TelegramLoginData, TokenResponse

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_via_trusted_bot(
        self, telegram_id: int, username: str | None
    ) -> TokenResponse:
        """
        Авторизация через доверенный источник (Бот).
        """
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user:
            user = User(telegram_id=telegram_id, username=username, role=UserRole.CANDIDATE)
            self.db.add(user)
            await self.db.flush()
            logger.info("New user registered via Bot", uid=user.id, tg_id=user.telegram_id)
        else:
            if username and user.username != username:
                user.username = username

        return await self._issue_tokens_for_user(user)

    async def authenticate_telegram(self, login_data: TelegramLoginData) -> TokenResponse:
        """
        1. Валидируем данные через Telegram Hash.
        2. Ищем или создаем юзера (Upsert).
        3. Выдаем токены.
        """
        data_dict = login_data.model_dump(exclude_none=True)

        is_valid = security.verify_telegram_data(data_dict, config.settings.TELEGRAM_BOT_TOKEN)
        if not is_valid:
            logger.warning("Invalid telegram hash", telegram_id=login_data.id)
            raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")

        stmt = select(User).where(User.telegram_id == login_data.id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user:
            user = User(
                telegram_id=login_data.id,
                username=login_data.username,
                role=UserRole.CANDIDATE,
            )
            self.db.add(user)
            await self.db.flush()
            logger.info("New user registered", uid=user.id, tg_id=user.telegram_id)
        else:
            if user.username != login_data.username:
                user.username = login_data.username

        return await self._issue_tokens_for_user(user)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        payload = security.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")

        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive or not found")

        return await self._issue_tokens_for_user(user)

    async def _issue_tokens_for_user(self, user: User) -> TokenResponse:
        access_payload = {
            "sub": str(user.id),
            "tg_id": user.telegram_id,
            "role": user.role.value,
        }
        refresh_payload = {"sub": str(user.id)}

        access_token = security.create_access_token(access_payload)
        refresh_token = security.create_refresh_token(refresh_payload)

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        db_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.fromtimestamp(security.decode_token(refresh_token)["exp"]),
        )
        self.db.add(db_token)
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
