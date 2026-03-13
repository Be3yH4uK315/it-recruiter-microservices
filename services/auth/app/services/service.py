import hashlib
from datetime import datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config, security
from app.models.auth import RefreshToken, User, UserRole
from app.schemas.auth import TelegramLoginData, TokenResponse

logger = structlog.get_logger()

MAX_ACTIVE_SESSIONS = 5


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_via_trusted_bot(
        self, telegram_id: int, username: str | None, role: UserRole | None = None
    ) -> TokenResponse:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        target_role = role or UserRole.CANDIDATE

        if not user:
            user = User(telegram_id=telegram_id, username=username, role=target_role)
            self.db.add(user)
            await self.db.flush()
            logger.info(
                "New user registered via Bot", uid=user.id, tg_id=user.telegram_id, role=target_role
            )
        else:
            if username and user.username != username:
                user.username = username
            if not user.is_active:
                raise HTTPException(status_code=403, detail="User is blocked")
            if role and user.role != role:
                user.role = role
                logger.info("User changed role", uid=user.id, new_role=role)

        return await self._issue_tokens_for_user(user)

    async def authenticate_telegram(self, login_data: TelegramLoginData) -> TokenResponse:
        data_dict = login_data.model_dump(exclude_none=True)

        is_valid = security.verify_telegram_data(data_dict, config.settings.TELEGRAM_BOT_TOKEN)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")

        stmt = select(User).where(User.telegram_id == login_data.id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        target_role = login_data.role or UserRole.CANDIDATE

        if not user:
            user = User(
                telegram_id=login_data.id,
                username=login_data.username,
                role=target_role,
            )
            self.db.add(user)
            await self.db.flush()
            logger.info("New user registered via WebApp", uid=user.id, tg_id=user.telegram_id)
        else:
            if user.username != login_data.username:
                user.username = login_data.username
            if not user.is_active:
                raise HTTPException(status_code=403, detail="User is blocked")
            if login_data.role and user.role != login_data.role:
                user.role = login_data.role

        return await self._issue_tokens_for_user(user)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        payload = security.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token structure")

        user_id = payload.get("sub")
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        stmt_token = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result_token = await self.db.execute(stmt_token)
        db_token = result_token.scalars().first()

        if not db_token:
            raise HTTPException(status_code=401, detail="Refresh token not found or already used")

        if db_token.revoked:
            raise HTTPException(status_code=401, detail="Refresh token was revoked")

        stmt_user = select(User).where(User.id == user_id)
        result_user = await self.db.execute(stmt_user)
        user = result_user.scalars().first()

        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="User inactive or not found")

        await self.db.delete(db_token)
        await self.db.flush()

        return await self._issue_tokens_for_user(user)

    async def logout(self, refresh_token: str):
        """Удаляет конкретную сессию (один токен)."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await self.db.execute(delete(RefreshToken).where(RefreshToken.token_hash == token_hash))
        await self.db.commit()

    async def logout_all(self, refresh_token: str):
        """Удаляет вообще все сессии пользователя, выкидывая его отовсюду."""
        payload = security.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")

        await self.db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        await self.db.commit()
        logger.info(f"User {user_id} logged out from all devices.")

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

        await self._cleanup_old_sessions(user.id)
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def _cleanup_old_sessions(self, user_id):
        stmt = (
            select(RefreshToken.id)
            .where(RefreshToken.user_id == user_id)
            .order_by(desc(RefreshToken.created_at))
        )
        result = await self.db.execute(stmt)
        session_ids = result.scalars().all()

        if len(session_ids) > MAX_ACTIVE_SESSIONS:
            ids_to_delete = session_ids[MAX_ACTIVE_SESSIONS:]
            del_stmt = delete(RefreshToken).where(RefreshToken.id.in_(ids_to_delete))
            await self.db.execute(del_stmt)
