from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.common.contracts import EventMapper
from app.domain.auth.entities import (
    RefreshSession,
    RefreshSessionIssued,
    RefreshSessionRevoked,
    User,
    UserAuthenticated,
    UserRegistered,
    UserRoleChanged,
)
from app.domain.common.events import DomainEvent


class DefaultEventMapper(EventMapper):
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        user: User | None = None,
        refresh_session: RefreshSession | None = None,
    ) -> list[tuple[str, dict]]:
        messages: list[tuple[str, dict]] = []

        user_id = user.id if user is not None else None

        base_payload = {
            "event_id": self._serialize_uuid(event.event_id),
            "occurred_at": self._serialize_dt(event.occurred_at),
            "event_name": event.event_name,
            "user_id": self._serialize_uuid(user_id),
        }

        if isinstance(event, UserRegistered):
            if user is None:
                return messages

            messages.append(
                (
                    "auth.user.created",
                    {
                        **base_payload,
                        "telegram_id": user.telegram_profile.telegram_id,
                        "active_role": user.role.value,
                        "roles": self._serialize_roles(user),
                        "is_active": user.is_active,
                        "snapshot": self._build_user_snapshot(user),
                    },
                )
            )
            return messages

        if isinstance(event, UserAuthenticated):
            if user is None:
                return messages

            messages.append(
                (
                    "auth.user.authenticated",
                    {
                        **base_payload,
                        "telegram_id": user.telegram_profile.telegram_id,
                        "active_role": user.role.value,
                        "roles": self._serialize_roles(user),
                        "provider": event.provider,
                    },
                )
            )
            return messages

        if isinstance(event, UserRoleChanged):
            if user is None:
                return messages

            messages.append(
                (
                    "auth.user.role_changed",
                    {
                        **base_payload,
                        "telegram_id": user.telegram_profile.telegram_id,
                        "old_role": event.old_role,
                        "new_role": event.new_role,
                        "active_role": user.role.value,
                        "roles": self._serialize_roles(user),
                    },
                )
            )
            return messages

        if isinstance(event, RefreshSessionIssued):
            session_id = refresh_session.id if refresh_session is not None else event.session_id
            messages.append(
                (
                    "auth.session.issued",
                    {
                        **base_payload,
                        "session_id": self._serialize_uuid(session_id),
                        "expires_at": self._serialize_optional_dt(event.expires_at),
                    },
                )
            )
            return messages

        if isinstance(event, RefreshSessionRevoked):
            session_id = refresh_session.id if refresh_session is not None else event.session_id
            messages.append(
                (
                    "auth.session.revoked",
                    {
                        **base_payload,
                        "session_id": self._serialize_uuid(session_id),
                    },
                )
            )
            return messages

        return messages

    def _build_user_snapshot(self, user: User) -> dict:
        return {
            "id": self._serialize_uuid(user.id),
            "telegram_id": user.telegram_profile.telegram_id,
            "username": user.telegram_profile.username,
            "first_name": user.telegram_profile.first_name,
            "last_name": user.telegram_profile.last_name,
            "photo_url": user.telegram_profile.photo_url,
            "active_role": user.role.value,
            "roles": self._serialize_roles(user),
            "is_active": user.is_active,
            "created_at": self._serialize_optional_dt(user.created_at),
            "updated_at": self._serialize_optional_dt(user.updated_at),
        }

    @staticmethod
    def _serialize_roles(user: User) -> list[str]:
        return sorted(role.value for role in user.roles)

    @staticmethod
    def _serialize_uuid(value: UUID | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _serialize_dt(value: datetime) -> str:
        return value.isoformat()

    @classmethod
    def _serialize_optional_dt(cls, value: datetime | None) -> str | None:
        if value is None:
            return None
        return cls._serialize_dt(value)
