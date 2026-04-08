from __future__ import annotations

from typing import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.auth.entities import User
from app.domain.auth.errors import UserNotFoundError


class GetUserByIdHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, user_id: UUID) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError(f"user {user_id} not found")
            return user
