from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.auth.entities import (
    RefreshSession,
    RefreshSessionIssued,
    RefreshSessionRevoked,
    User,
    UserAuthenticated,
    UserRegistered,
    UserRoleChanged,
)
from app.domain.auth.enums import AuthProvider, UserRole
from app.domain.auth.errors import UserInactiveError
from app.domain.auth.value_objects import TelegramProfile


def test_user_register_creates_registered_event() -> None:
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

    events = user.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], UserRegistered)
    assert events[0].user_id == user.id
    assert events[0].telegram_id == 1001
    assert events[0].role == UserRole.EMPLOYER.value


def test_pull_events_clears_user_events() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )

    first = user.pull_events()
    second = user.pull_events()

    assert len(first) == 1
    assert second == []


def test_user_update_telegram_profile_updates_fields_and_timestamp() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(
            telegram_id=1001,
            username="old_user",
        ),
        role=UserRole.EMPLOYER,
    )
    initial_updated_at = user.updated_at

    user.update_telegram_profile(
        TelegramProfile(
            telegram_id=1001,
            username="new_user",
            first_name="Alice",
            last_name="HR",
            photo_url="https://example.com/new.jpg",
        )
    )

    assert user.telegram_profile.username == "new_user"
    assert user.telegram_profile.first_name == "Alice"
    assert user.telegram_profile.last_name == "HR"
    assert user.telegram_profile.photo_url == "https://example.com/new.jpg"
    assert user.updated_at >= initial_updated_at


def test_user_change_role_adds_event_when_role_changes() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )
    user.pull_events()

    user.change_role(UserRole.CANDIDATE)

    events = user.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], UserRoleChanged)
    assert events[0].old_role == UserRole.EMPLOYER.value
    assert events[0].new_role == UserRole.CANDIDATE.value


def test_user_change_role_does_nothing_for_same_role() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )
    user.pull_events()

    user.change_role(UserRole.EMPLOYER)

    assert user.pull_events() == []


def test_user_mark_authenticated_adds_event() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )
    user.pull_events()

    user.mark_authenticated(AuthProvider.BOT)

    events = user.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], UserAuthenticated)
    assert events[0].user_id == user.id
    assert events[0].telegram_id == 1001
    assert events[0].provider == AuthProvider.BOT.value
    assert events[0].role == UserRole.EMPLOYER.value


def test_user_ensure_active_raises_for_inactive_user() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )
    user.is_active = False

    with pytest.raises(UserInactiveError, match="user is inactive"):
        user.ensure_active()


def test_user_mark_authenticated_raises_for_inactive_user() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1001),
        role=UserRole.EMPLOYER,
    )
    user.is_active = False
    user.pull_events()

    with pytest.raises(UserInactiveError, match="user is inactive"):
        user.mark_authenticated(AuthProvider.TELEGRAM)


def test_refresh_session_issue_creates_event() -> None:
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash-value",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    events = session.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], RefreshSessionIssued)
    assert events[0].session_id == session.id
    assert events[0].user_id == session.user_id
    assert events[0].expires_at == session.expires_at


def test_refresh_session_revoke_adds_event_once() -> None:
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash-value",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.pull_events()

    session.revoke()
    session.revoke()

    events = session.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], RefreshSessionRevoked)
    assert session.revoked is True


def test_refresh_session_is_expired_true_for_past() -> None:
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash-value",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    assert session.is_expired() is True


def test_refresh_session_is_expired_false_for_future() -> None:
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hash-value",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    assert session.is_expired() is False
