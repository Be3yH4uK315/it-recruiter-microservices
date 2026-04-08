from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.auth.entities import (
    RefreshSession,
    User,
)
from app.domain.auth.enums import AuthProvider, UserRole
from app.domain.auth.value_objects import TelegramProfile
from app.infrastructure.messaging.event_mapper import DefaultEventMapper


def test_event_mapper_maps_user_registered_event() -> None:
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
    event = user.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event, user=user)

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "auth.user.created"
    assert payload["event_name"] == "user_registered"
    assert payload["user_id"] == str(user.id)
    assert payload["telegram_id"] == 1001
    assert payload["active_role"] == "employer"
    assert payload["snapshot"]["id"] == str(user.id)


def test_event_mapper_maps_user_authenticated_event() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1002),
        role=UserRole.CANDIDATE,
    )
    user.pull_events()

    user.mark_authenticated(AuthProvider.BOT)
    event = user.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event, user=user)

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "auth.user.authenticated"
    assert payload["provider"] == "bot"
    assert payload["active_role"] == "candidate"


def test_event_mapper_maps_user_role_changed_event() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1003),
        role=UserRole.EMPLOYER,
    )
    user.pull_events()

    user.change_role(UserRole.ADMIN)
    event = user.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event, user=user)

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "auth.user.role_changed"
    assert payload["old_role"] == "employer"
    assert payload["new_role"] == "admin"


def test_event_mapper_maps_refresh_session_issued_event() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1004),
        role=UserRole.EMPLOYER,
    )
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=user.id,
        token_hash="hash-1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    event = session.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(
        event=event,
        user=user,
        refresh_session=session,
    )

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "auth.session.issued"
    assert payload["session_id"] == str(session.id)
    assert payload["user_id"] == str(user.id)
    assert payload["expires_at"] is not None


def test_event_mapper_maps_refresh_session_revoked_event() -> None:
    user = User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(telegram_id=1005),
        role=UserRole.EMPLOYER,
    )
    session = RefreshSession.issue(
        id=uuid4(),
        user_id=user.id,
        token_hash="hash-1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.pull_events()

    session.revoke()
    event = session.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(
        event=event,
        user=user,
        refresh_session=session,
    )

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "auth.session.revoked"
    assert payload["session_id"] == str(session.id)
    assert payload["user_id"] == str(user.id)


def test_event_mapper_returns_empty_list_for_unknown_event() -> None:
    from app.domain.common.events import DomainEvent

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=DomainEvent())

    assert messages == []
