from __future__ import annotations

from typing import Callable

from app.application.common.uow import UnitOfWork
from app.domain.auth.entities import User
from app.domain.auth.errors import UserNotFoundError


class GetUserByTelegramIdHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, telegram_id: int) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_telegram_id(telegram_id)
            if user is None:
                raise UserNotFoundError(f"user with telegram_id={telegram_id} not found")
            return user
