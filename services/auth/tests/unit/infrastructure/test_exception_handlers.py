from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.auth.errors import (
    InvalidRefreshTokenError,
    InvalidTelegramAuthError,
    RefreshSessionRevokedError,
    UserInactiveError,
    UserNotFoundError,
)
from app.infrastructure.web.exception_handlers import register_exception_handlers


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    return app


def test_user_not_found_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise UserNotFoundError("missing")

    client = TestClient(app)
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found", "request_id": None}


def test_invalid_telegram_auth_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise InvalidTelegramAuthError("telegram auth hash mismatch")

    client = TestClient(app)
    response = client.get("/boom")

    assert response.status_code == 401
    assert response.json() == {"detail": "telegram auth hash mismatch", "request_id": None}


def test_invalid_refresh_token_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise InvalidRefreshTokenError("invalid token")

    client = TestClient(app)
    response = client.get("/boom")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid token", "request_id": None}


def test_refresh_session_revoked_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RefreshSessionRevokedError("refresh session is revoked")

    client = TestClient(app)
    response = client.get("/boom")

    assert response.status_code == 401
    assert response.json() == {"detail": "refresh session is revoked", "request_id": None}


def test_user_inactive_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise UserInactiveError("user is inactive")

    client = TestClient(app)
    response = client.get("/boom")

    assert response.status_code == 403
    assert response.json() == {"detail": "user is inactive", "request_id": None}


def test_unhandled_exception_handler() -> None:
    app = build_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("unexpected")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "request_id": None}
