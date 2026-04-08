from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.auth.entities import RefreshSession, User


class AuthUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, user: User) -> None:
        raise NotImplementedError


class RefreshSessionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> RefreshSession | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user_id(self, user_id: UUID) -> list[RefreshSession]:
        raise NotImplementedError

    @abstractmethod
    async def list_active_by_user_id(
        self,
        user_id: UUID,
        *,
        now: datetime,
    ) -> list[RefreshSession]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, session: RefreshSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, session: RefreshSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, session_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_all_by_user_id(self, user_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_expired_or_revoked_by_user_id(
        self,
        user_id: UUID,
        *,
        now: datetime,
    ) -> None:
        raise NotImplementedError
