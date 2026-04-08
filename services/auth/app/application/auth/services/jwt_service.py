from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from jwt import InvalidTokenError

from app.config import Settings
from app.domain.auth.entities import User
from app.domain.auth.enums import TokenType, UserRole
from app.domain.auth.errors import InvalidAccessTokenError, InvalidRefreshTokenError
from app.domain.auth.value_objects import AccessTokenClaims, RefreshTokenClaims


class JwtService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def access_token_ttl_seconds(self) -> int:
        return self._settings.access_token_expire_minutes * 60

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self._settings.refresh_token_expire_days * 24 * 60 * 60

    def build_access_expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes,
        )

    def build_refresh_expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days,
        )

    def create_access_token(self, *, user: User) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = self.build_access_expires_at()

        payload = {
            "sub": str(user.id),
            "telegram_id": user.telegram_profile.telegram_id,
            "role": user.role.value,
            "type": TokenType.ACCESS.value,
            "jti": str(uuid4()),
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )
        return token, expires_at

    def create_refresh_token(self, *, session_id: str, expires_at: datetime) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": session_id,
            "type": TokenType.REFRESH.value,
            "iat": now,
            "exp": expires_at,
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        payload = self._decode_token(
            token=token,
            expected_type=TokenType.ACCESS,
            invalid_token_error_cls=InvalidAccessTokenError,
        )

        try:
            subject = str(payload["sub"])
            telegram_id = int(payload["telegram_id"])
            role = UserRole(str(payload["role"]))
            expires_at = self._normalize_exp(payload["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError("invalid access token payload") from exc

        return AccessTokenClaims(
            subject=subject,
            telegram_id=telegram_id,
            role=role,
            expires_at=expires_at,
        )

    def decode_refresh_token(self, token: str) -> RefreshTokenClaims:
        payload = self._decode_token(
            token=token,
            expected_type=TokenType.REFRESH,
            invalid_token_error_cls=InvalidRefreshTokenError,
        )

        try:
            subject = str(payload["sub"])
            expires_at = self._normalize_exp(payload["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidRefreshTokenError("invalid refresh token payload") from exc

        return RefreshTokenClaims(
            subject=subject,
            expires_at=expires_at,
        )

    def _decode_token(
        self,
        *,
        token: str,
        expected_type: TokenType,
        invalid_token_error_cls: type[InvalidAccessTokenError] | type[InvalidRefreshTokenError],
    ) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except InvalidTokenError as exc:
            raise invalid_token_error_cls("invalid token") from exc

        if not isinstance(payload, dict):
            raise invalid_token_error_cls("invalid token payload")

        token_type = payload.get("type")
        if token_type != expected_type.value:
            raise invalid_token_error_cls("invalid token type")

        return payload

    @staticmethod
    def _normalize_exp(value: int | float | datetime) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

        raise ValueError("invalid exp value")
