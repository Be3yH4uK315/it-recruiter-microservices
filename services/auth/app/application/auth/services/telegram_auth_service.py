from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from app.config import Settings
from app.domain.auth.errors import InvalidTelegramAuthError
from app.domain.auth.value_objects import TelegramProfile


class TelegramAuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate_auth_payload(self, payload: dict[str, str]) -> TelegramProfile:
        if not self._settings.telegram_bot_token.strip():
            raise InvalidTelegramAuthError("telegram bot token is not configured")

        normalized_payload = self._normalize_payload(payload)

        auth_hash = normalized_payload.get("hash")
        auth_date_raw = normalized_payload.get("auth_date")
        user_id_raw = normalized_payload.get("id")

        if not auth_hash:
            raise InvalidTelegramAuthError("missing telegram auth hash")
        if not auth_date_raw:
            raise InvalidTelegramAuthError("missing telegram auth date")
        if not user_id_raw:
            raise InvalidTelegramAuthError("missing telegram user id")

        try:
            auth_timestamp = int(auth_date_raw)
        except (TypeError, ValueError) as exc:
            raise InvalidTelegramAuthError("invalid telegram auth date") from exc

        now_ts = int(datetime.now(timezone.utc).timestamp())
        age_seconds = now_ts - auth_timestamp
        if age_seconds < 0 or age_seconds > self._settings.telegram_auth_max_age_seconds:
            raise InvalidTelegramAuthError("telegram auth payload is expired")

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(normalized_payload.items())
            if key != "hash" and value is not None
        )

        secret_key = hashlib.sha256(self._settings.telegram_bot_token.encode("utf-8")).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, auth_hash):
            raise InvalidTelegramAuthError("telegram auth hash mismatch")

        try:
            telegram_id = int(user_id_raw)
        except (TypeError, ValueError) as exc:
            raise InvalidTelegramAuthError("invalid telegram user id") from exc

        if telegram_id <= 0:
            raise InvalidTelegramAuthError("invalid telegram user id")

        return TelegramProfile(
            telegram_id=telegram_id,
            username=normalized_payload.get("username"),
            first_name=normalized_payload.get("first_name"),
            last_name=normalized_payload.get("last_name"),
            photo_url=normalized_payload.get("photo_url"),
        )

    @staticmethod
    def _normalize_payload(payload: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}

        for key, value in payload.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue

            normalized_value = str(value).strip()
            if normalized_value == "":
                continue

            normalized[normalized_key] = normalized_value

        return normalized
