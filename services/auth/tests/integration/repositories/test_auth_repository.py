from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.entities import RefreshSession, User
from app.domain.auth.enums import UserRole
from app.domain.auth.errors import RefreshSessionNotFoundError, UserNotFoundError
from app.domain.auth.value_objects import TelegramProfile
from app.infrastructure.db.repositories.auth import (
    SqlAlchemyAuthUserRepository,
    SqlAlchemyRefreshSessionRepository,
)


@pytest.mark.asyncio
async def test_user_repository_add_and_get_by_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        user = User.register(
            id=uuid4(),
            telegram_profile=TelegramProfile(
                telegram_id=1001,
                username="alice",
                first_name="Alice",
                last_name="HR",
                photo_url="https://example.com/avatar.jpg",
            ),
            role=UserRole.EMPLOYER,
        )

        await repo.add(user)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        loaded = await repo.get_by_id(user.id)

        assert loaded is not None
        assert loaded.id == user.id
        assert loaded.telegram_profile.telegram_id == 1001
        assert loaded.telegram_profile.username == "alice"
        assert loaded.role == UserRole.EMPLOYER
        assert loaded.is_active is True


@pytest.mark.asyncio
async def test_user_repository_get_by_telegram_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        user = User.register(
            id=uuid4(),
            telegram_profile=TelegramProfile(telegram_id=2002, username="bob"),
            role=UserRole.CANDIDATE,
        )

        await repo.add(user)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        loaded = await repo.get_by_telegram_id(2002)

        assert loaded is not None
        assert loaded.id == user.id
        assert loaded.telegram_profile.telegram_id == 2002
        assert loaded.role == UserRole.CANDIDATE


@pytest.mark.asyncio
async def test_user_repository_save_updates_existing_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()

    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(
                telegram_id=3003,
                username="old_user",
            ),
            role=UserRole.EMPLOYER,
        )

        await repo.add(user)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        loaded = await repo.get_by_id(user_id)
        assert loaded is not None

        loaded.update_telegram_profile(
            TelegramProfile(
                telegram_id=3003,
                username="new_user",
                first_name="Updated",
                last_name="Name",
                photo_url="https://example.com/new.jpg",
            )
        )
        loaded.change_role(UserRole.ADMIN)

        await repo.save(loaded)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        updated = await repo.get_by_id(user_id)

        assert updated is not None
        assert updated.telegram_profile.username == "new_user"
        assert updated.telegram_profile.first_name == "Updated"
        assert updated.telegram_profile.last_name == "Name"
        assert updated.telegram_profile.photo_url == "https://example.com/new.jpg"
        assert updated.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_user_repository_save_raises_for_missing_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyAuthUserRepository(session)
        user = User.register(
            id=uuid4(),
            telegram_profile=TelegramProfile(telegram_id=4004),
            role=UserRole.EMPLOYER,
        )

        with pytest.raises(UserNotFoundError, match="not found"):
            await repo.save(user)


@pytest.mark.asyncio
async def test_refresh_session_repository_add_and_get(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()
    session_id = uuid4()

    async with session_factory() as session:
        user_repo = SqlAlchemyAuthUserRepository(session)
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(telegram_id=5005),
            role=UserRole.EMPLOYER,
        )
        await user_repo.add(user)

        refresh_session = RefreshSession.issue(
            id=session_id,
            user_id=user_id,
            token_hash="hash-1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await refresh_repo.add(refresh_session)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        by_id = await refresh_repo.get_by_id(session_id)
        by_hash = await refresh_repo.get_by_token_hash("hash-1")

        assert by_id is not None
        assert by_hash is not None
        assert by_id.id == session_id
        assert by_hash.id == session_id
        assert by_id.user_id == user_id
        assert by_id.token_hash == "hash-1"
        assert by_id.revoked is False


@pytest.mark.asyncio
async def test_refresh_session_repository_list_by_user_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()

    async with session_factory() as session:
        user_repo = SqlAlchemyAuthUserRepository(session)
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(telegram_id=6006),
            role=UserRole.EMPLOYER,
        )
        await user_repo.add(user)

        first = RefreshSession.issue(
            id=uuid4(),
            user_id=user_id,
            token_hash="hash-a",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        second = RefreshSession.issue(
            id=uuid4(),
            user_id=user_id,
            token_hash="hash-b",
            expires_at=datetime.now(timezone.utc) + timedelta(days=8),
        )

        await refresh_repo.add(first)
        await refresh_repo.add(second)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        items = await refresh_repo.list_by_user_id(user_id)

        assert len(items) == 2
        assert {item.token_hash for item in items} == {"hash-a", "hash-b"}


@pytest.mark.asyncio
async def test_refresh_session_repository_save_updates_existing_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()
    refresh_id = uuid4()

    async with session_factory() as session:
        user_repo = SqlAlchemyAuthUserRepository(session)
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(telegram_id=7007),
            role=UserRole.EMPLOYER,
        )
        await user_repo.add(user)

        refresh_session = RefreshSession.issue(
            id=refresh_id,
            user_id=user_id,
            token_hash="hash-initial",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await refresh_repo.add(refresh_session)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        loaded = await refresh_repo.get_by_id(refresh_id)
        assert loaded is not None

        loaded.revoke()
        await refresh_repo.save(loaded)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        updated = await refresh_repo.get_by_id(refresh_id)

        assert updated is not None
        assert updated.revoked is True


@pytest.mark.asyncio
async def test_refresh_session_repository_save_raises_for_missing_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        refresh_session = RefreshSession.issue(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hash-missing",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        with pytest.raises(RefreshSessionNotFoundError, match="not found"):
            await refresh_repo.save(refresh_session)


@pytest.mark.asyncio
async def test_refresh_session_repository_delete(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()
    refresh_id = uuid4()

    async with session_factory() as session:
        user_repo = SqlAlchemyAuthUserRepository(session)
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(telegram_id=8008),
            role=UserRole.EMPLOYER,
        )
        await user_repo.add(user)

        refresh_session = RefreshSession.issue(
            id=refresh_id,
            user_id=user_id,
            token_hash="hash-delete",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await refresh_repo.add(refresh_session)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        await refresh_repo.delete(refresh_id)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        loaded = await refresh_repo.get_by_id(refresh_id)

        assert loaded is None


@pytest.mark.asyncio
async def test_refresh_session_repository_delete_all_by_user_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid4()

    async with session_factory() as session:
        user_repo = SqlAlchemyAuthUserRepository(session)
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)

        user = User.register(
            id=user_id,
            telegram_profile=TelegramProfile(telegram_id=9009),
            role=UserRole.EMPLOYER,
        )
        await user_repo.add(user)

        first = RefreshSession.issue(
            id=uuid4(),
            user_id=user_id,
            token_hash="hash-1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        second = RefreshSession.issue(
            id=uuid4(),
            user_id=user_id,
            token_hash="hash-2",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        await refresh_repo.add(first)
        await refresh_repo.add(second)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        await refresh_repo.delete_all_by_user_id(user_id)
        await session.commit()

    async with session_factory() as session:
        refresh_repo = SqlAlchemyRefreshSessionRepository(session)
        items = await refresh_repo.list_by_user_id(user_id)

        assert items == []
