from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.auth.entities import RefreshSession, User
from app.domain.auth.enums import UserRole
from app.domain.auth.errors import RefreshSessionNotFoundError, UserNotFoundError
from app.domain.auth.repository import AuthUserRepository, RefreshSessionRepository
from app.domain.auth.value_objects import TelegramProfile
from app.infrastructure.db.models.auth import (
    RefreshSessionModel,
    UserModel,
    UserRoleBindingModel,
)


class SqlAlchemyAuthUserRepository(AuthUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.role_bindings))
            .where(UserModel.id == user_id)
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        return None if orm_obj is None else self._to_domain(orm_obj)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.role_bindings))
            .where(UserModel.telegram_id == telegram_id)
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        return None if orm_obj is None else self._to_domain(orm_obj)

    async def add(self, user: User) -> None:
        self._session.add(self._to_orm(user))

    async def save(self, user: User) -> None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.role_bindings))
            .where(UserModel.id == user.id)
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise UserNotFoundError(f"user {user.id} not found")

        orm_obj.telegram_id = user.telegram_profile.telegram_id
        orm_obj.username = user.telegram_profile.username
        orm_obj.first_name = user.telegram_profile.first_name
        orm_obj.last_name = user.telegram_profile.last_name
        orm_obj.photo_url = user.telegram_profile.photo_url
        orm_obj.role = user.role.value
        orm_obj.is_active = user.is_active
        orm_obj.updated_at = self._normalize_datetime(user.updated_at)

        desired_roles = {role.value for role in user.roles}
        existing_roles = {binding.role for binding in orm_obj.role_bindings}

        for binding in list(orm_obj.role_bindings):
            if binding.role not in desired_roles:
                orm_obj.role_bindings.remove(binding)

        for missing_role in sorted(desired_roles - existing_roles):
            orm_obj.role_bindings.append(
                UserRoleBindingModel(
                    user_id=user.id,
                    role=missing_role,
                )
            )

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        role_bindings = getattr(model, "role_bindings", None) or []
        roles = frozenset(UserRole(binding.role) for binding in role_bindings) or frozenset(
            {UserRole(model.role)}
        )

        return User(
            id=model.id,
            telegram_profile=TelegramProfile(
                telegram_id=model.telegram_id,
                username=model.username,
                first_name=model.first_name,
                last_name=model.last_name,
                photo_url=model.photo_url,
            ),
            role=UserRole(model.role),
            roles=roles,
            is_active=model.is_active,
            created_at=SqlAlchemyAuthUserRepository._normalize_datetime(model.created_at),
            updated_at=SqlAlchemyAuthUserRepository._normalize_datetime(model.updated_at),
        )

    @staticmethod
    def _to_orm(entity: User) -> UserModel:
        role_bindings = [
            UserRoleBindingModel(role=role.value)
            for role in sorted(entity.roles, key=lambda item: item.value)
        ]

        return UserModel(
            id=entity.id,
            telegram_id=entity.telegram_profile.telegram_id,
            username=entity.telegram_profile.username,
            first_name=entity.telegram_profile.first_name,
            last_name=entity.telegram_profile.last_name,
            photo_url=entity.telegram_profile.photo_url,
            role=entity.role.value,
            is_active=entity.is_active,
            created_at=SqlAlchemyAuthUserRepository._normalize_datetime(entity.created_at),
            updated_at=SqlAlchemyAuthUserRepository._normalize_datetime(entity.updated_at),
            role_bindings=role_bindings,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SqlAlchemyRefreshSessionRepository(RefreshSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: UUID) -> RefreshSession | None:
        stmt = select(RefreshSessionModel).where(RefreshSessionModel.id == session_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        return None if orm_obj is None else self._to_domain(orm_obj)

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        stmt = select(RefreshSessionModel).where(RefreshSessionModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        return None if orm_obj is None else self._to_domain(orm_obj)

    async def list_by_user_id(self, user_id: UUID) -> list[RefreshSession]:
        stmt = (
            select(RefreshSessionModel)
            .where(RefreshSessionModel.user_id == user_id)
            .order_by(RefreshSessionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(item) for item in result.scalars().all()]

    async def list_active_by_user_id(
        self,
        user_id: UUID,
        *,
        now: datetime,
    ) -> list[RefreshSession]:
        normalized_now = self._normalize_datetime(now)
        stmt = (
            select(RefreshSessionModel)
            .where(
                and_(
                    RefreshSessionModel.user_id == user_id,
                    RefreshSessionModel.revoked.is_(False),
                    RefreshSessionModel.expires_at > normalized_now,
                )
            )
            .order_by(RefreshSessionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(item) for item in result.scalars().all()]

    async def add(self, session: RefreshSession) -> None:
        self._session.add(self._to_orm(session))

    async def save(self, session: RefreshSession) -> None:
        stmt = select(RefreshSessionModel).where(RefreshSessionModel.id == session.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise RefreshSessionNotFoundError(f"refresh session {session.id} not found")

        orm_obj.token_hash = session.token_hash
        orm_obj.expires_at = self._normalize_datetime(session.expires_at)
        orm_obj.revoked = session.revoked

    async def delete(self, session_id: UUID) -> None:
        stmt = delete(RefreshSessionModel).where(RefreshSessionModel.id == session_id)
        await self._session.execute(stmt)

    async def delete_all_by_user_id(self, user_id: UUID) -> None:
        stmt = delete(RefreshSessionModel).where(RefreshSessionModel.user_id == user_id)
        await self._session.execute(stmt)

    async def delete_expired_or_revoked_by_user_id(
        self,
        user_id: UUID,
        *,
        now: datetime,
    ) -> None:
        normalized_now = self._normalize_datetime(now)
        stmt = delete(RefreshSessionModel).where(
            and_(
                RefreshSessionModel.user_id == user_id,
                or_(
                    RefreshSessionModel.revoked.is_(True),
                    RefreshSessionModel.expires_at <= normalized_now,
                ),
            )
        )
        await self._session.execute(stmt)

    @staticmethod
    def _to_domain(model: RefreshSessionModel) -> RefreshSession:
        return RefreshSession(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=SqlAlchemyRefreshSessionRepository._normalize_datetime(model.expires_at),
            revoked=model.revoked,
            created_at=SqlAlchemyRefreshSessionRepository._normalize_datetime(model.created_at),
        )

    @staticmethod
    def _to_orm(entity: RefreshSession) -> RefreshSessionModel:
        return RefreshSessionModel(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=SqlAlchemyRefreshSessionRepository._normalize_datetime(entity.expires_at),
            revoked=entity.revoked,
            created_at=SqlAlchemyRefreshSessionRepository._normalize_datetime(entity.created_at),
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
