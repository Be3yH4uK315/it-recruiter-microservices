from __future__ import annotations

import os

os.environ["DEBUG"] = "false"

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.http.v1.api import api_router
from app.api.http.v1.dependencies import (
    get_app_settings,
    get_db_session,
    get_settings_dependency,
    get_update_router_service,
)
from app.config import Settings
from app.infrastructure.telegram.client import TelegramApiError


@dataclass
class FakeConversationState:
    role_context: str | None
    state_key: str | None
    state_version: int | None
    payload: dict | None
    updated_at: datetime | None


class FakeResult:
    def __init__(self, state: FakeConversationState | None) -> None:
        self._state = state

    def scalar_one_or_none(self) -> FakeConversationState | None:
        return self._state


class FakeSession:
    def __init__(self, state: FakeConversationState | None) -> None:
        self._state = state

    async def execute(self, _stmt):
        return FakeResult(self._state)


class FakeUpdateRouterService:
    def __init__(self, result: dict | Exception) -> None:
        self._result = result
        self.calls = []

    async def route(self, update) -> dict:
        self.calls.append(update)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def build_test_app(
    *,
    settings: Settings,
    state_for_internal: FakeConversationState | None = None,
    webhook_result: dict | None = None,
) -> tuple[FastAPI, FakeUpdateRouterService]:
    app = FastAPI()
    app.include_router(api_router)
    app.state.settings = settings

    router_service = FakeUpdateRouterService(result=webhook_result or {"handled": True})

    async def override_db_session():
        yield FakeSession(state_for_internal)

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_settings_dependency] = lambda: settings
    app.dependency_overrides[get_update_router_service] = lambda: router_service
    return app, router_service


def test_health_returns_service_metadata() -> None:
    settings = Settings(app_name="bot-service", app_version="1.2.3", app_env="test")
    app, _ = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "bot-service",
        "version": "1.2.3",
        "environment": "test",
    }


def test_internal_state_requires_configured_internal_token() -> None:
    settings = Settings(internal_service_token=None)
    app, _ = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/internal/state/100")

    assert response.status_code == 503
    assert response.json()["detail"] == "Internal service token is not configured"


def test_internal_state_requires_bearer_header() -> None:
    settings = Settings(internal_service_token="internal-token")
    app, _ = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/internal/state/100")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing internal bearer token"


def test_internal_state_rejects_invalid_token() -> None:
    settings = Settings(internal_service_token="internal-token")
    app, _ = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/internal/state/100",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal bearer token"


def test_internal_state_returns_state_payload() -> None:
    settings = Settings(internal_service_token="internal-token")
    state = FakeConversationState(
        role_context="candidate",
        state_key="profile_edit",
        state_version=2,
        payload={"step": 3},
        updated_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
    )
    app, _ = build_test_app(settings=settings, state_for_internal=state)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/internal/state/100",
            headers={"Authorization": "Bearer internal-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram_user_id"] == 100
    assert payload["state"]["role_context"] == "candidate"
    assert payload["state"]["state_key"] == "profile_edit"
    assert payload["state"]["state_version"] == 2
    assert payload["state"]["payload"] == {"step": 3}
    assert payload["state"]["updated_at"] == "2026-04-03T12:00:00+00:00"


def test_webhook_rejects_invalid_secret_token() -> None:
    settings = Settings(telegram_webhook_secret_token="secret")
    app, router_service = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 1, "message": {"message_id": 10}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid telegram webhook secret token"
    assert router_service.calls == []


def test_webhook_accepts_valid_secret_token_and_returns_handler_result() -> None:
    settings = Settings(telegram_webhook_secret_token="secret")
    app, router_service = build_test_app(
        settings=settings,
        webhook_result={"handled": True, "update_type": "message"},
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telegram/webhook",
            json={
                "update_id": 1,
                "message": {
                    "message_id": 10,
                    "from": {"id": 123, "is_bot": False, "first_name": "Test"},
                    "chat": {"id": 123, "type": "private"},
                    "text": "hello",
                },
            },
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"] == {"handled": True, "update_type": "message"}
    assert len(router_service.calls) == 1


def test_webhook_without_configured_secret_allows_request() -> None:
    settings = Settings(telegram_webhook_secret_token=None)
    app, router_service = build_test_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telegram/webhook",
            json={
                "update_id": 2,
                "callback_query": {
                    "id": "cb1",
                    "from": {"id": 321, "is_bot": False, "first_name": "A"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(router_service.calls) == 1


def test_webhook_returns_degraded_ack_for_placeholder_bot_token() -> None:
    settings = Settings(
        app_env="docker",
        telegram_bot_token="change-me-telegram-bot-token",
        telegram_webhook_secret_token=None,
    )
    app, router_service = build_test_app(
        settings=settings,
        webhook_result=TelegramApiError("telegram api request failed for method sendMessage"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telegram/webhook",
            json={
                "update_id": 3,
                "message": {
                    "message_id": 10,
                    "from": {"id": 123, "is_bot": False, "first_name": "Test"},
                    "chat": {"id": 123, "type": "private"},
                    "text": "/start",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["result"] == {
        "status": "degraded",
        "reason": "telegram_api_unavailable",
        "update_id": 3,
    }
    assert len(router_service.calls) == 1
