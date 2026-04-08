from __future__ import annotations

import re
from urllib.parse import urlparse

from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class CommonUtilsMixin:
    _EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    _TELEGRAM_HANDLE_RE = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
    _PROFILE_NAME_MIN_LEN = 2
    _PROFILE_NAME_ALLOWED_EXTRA_CHARS = {" ", ".", ",", "'", "’", "&", "(", ")", "-", "/"}
    _PROFILE_NAME_ALLOWED_EXTRA_CHARS_TEXT = " .,'’&()/-"
    _PROFILE_NAME_ALLOWED_EXTRA_CHARS_PROMPT = "буквы, цифры, пробелы и символы `.-,'’&()/`"

    @staticmethod
    def _resolve_chat_id(callback: TelegramCallbackQuery, actor: TelegramUser) -> int:
        if callback.message is not None and callback.message.chat is not None:
            return callback.message.chat.id
        return actor.id

    @staticmethod
    def _extract_payload_text(payload: dict | None, key: str) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _build_telegram_contact(actor: TelegramUser) -> str:
        if actor.username:
            return f"@{actor.username}"
        return f"id:{actor.id}"

    @classmethod
    def _normalize_contact_value(
        cls,
        *,
        contact_key: str,
        raw_value: str | None,
    ) -> tuple[str | None, str | None]:
        if raw_value is None:
            return None, None

        normalized = str(raw_value).strip()
        if not normalized:
            return None, "Пустое значение сохранить нельзя. Отправь `-`, чтобы очистить поле."

        if contact_key == "email":
            if not cls._EMAIL_RE.match(normalized):
                return None, "Некорректный email. Пример: `name@example.com`."
            return normalized.lower(), None

        if contact_key == "phone":
            digits = re.sub(r"\D", "", normalized)
            if len(digits) == 11 and digits[0] in {"7", "8"}:
                return f"+7{digits[1:]}", None
            if len(digits) == 10:
                return f"+7{digits}", None
            if normalized.startswith("+") and 10 <= len(digits) <= 15:
                return "+" + digits, None
            return None, "Некорректный номер телефона. Пример: `+7 999 123-45-67`."

        if contact_key == "website":
            candidate = normalized
            if not candidate.lower().startswith(("http://", "https://")):
                candidate = f"https://{candidate}"
            parsed = urlparse(candidate)
            hostname = parsed.hostname
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or hostname is None:
                return (
                    None,
                    "Некорректный сайт. Пример: `https://company.com`. "
                    "Ссылка должна начинаться с `http://` или `https://` и содержать домен.",
                )
            if hostname.startswith(".") or hostname.endswith("."):
                return (
                    None,
                    "Некорректный сайт. Пример: `https://company.com`. "
                    "Ссылка должна начинаться с `http://` или `https://` и содержать домен.",
                )
            if any(not label for label in hostname.split(".")):
                return (
                    None,
                    "Некорректный сайт. Пример: `https://company.com`. "
                    "Ссылка должна начинаться с `http://` или `https://` и содержать домен.",
                )
            if not all(ch.isalnum() or ch in {"-", "."} for ch in hostname):
                return (
                    None,
                    "Некорректный сайт. Пример: `https://company.com`. "
                    "Ссылка должна начинаться с `http://` или `https://` и содержать домен.",
                )
            return candidate, None

        if contact_key == "telegram":
            handle = normalized
            if handle.lower().startswith(("https://t.me/", "http://t.me/", "t.me/")):
                handle = handle.split("t.me/")[-1].strip("/")
            if not cls._TELEGRAM_HANDLE_RE.match(handle):
                return None, "Некорректный Telegram-контакт. Пример: `@company_hr`."
            return handle if handle.startswith("@") else f"@{handle}", None

        return normalized, None

    @classmethod
    def _normalize_profile_name_value(
        cls,
        *,
        raw_value: str | None,
        field_label: str,
    ) -> tuple[str | None, str | None]:
        if raw_value is None:
            return None, None

        normalized = str(raw_value).strip()
        if len(normalized) < cls._PROFILE_NAME_MIN_LEN:
            return (
                None,
                f"{field_label} должно быть не короче {cls._PROFILE_NAME_MIN_LEN} символов. "
                "Например: `Иван Петров` или `Acme Labs`.",
            )

        if not any(ch.isalnum() for ch in normalized):
            return (
                None,
                f"{field_label} должно содержать хотя бы одну букву или цифру, "
                "а не только знаки препинания.",
            )

        if not all(
            ch.isalnum() or ch in cls._PROFILE_NAME_ALLOWED_EXTRA_CHARS for ch in normalized
        ):
            return (
                None,
                f"{field_label} содержит недопустимые символы. "
                "Можно использовать буквы, цифры, пробелы и символы "
                f"`{cls._PROFILE_NAME_ALLOWED_EXTRA_CHARS_TEXT}`.",
            )

        return normalized, None

    @classmethod
    def _build_profile_name_prompt(
        cls,
        *,
        field_label: str,
        example: str,
        allow_clear: bool = True,
    ) -> str:
        prompt = (
            f"Введи {field_label}. Минимум {cls._PROFILE_NAME_MIN_LEN} символа. "
            f"Можно использовать {cls._PROFILE_NAME_ALLOWED_EXTRA_CHARS_PROMPT}."
        )
        if example:
            prompt = f"{prompt} Например: `{example}`."
        if allow_clear:
            prompt = f"{prompt} Чтобы очистить поле, отправь `-`."
        return prompt

    @staticmethod
    def _build_profile_contact_prompt(
        *,
        contact_label: str,
        example: str,
        allow_clear: bool = True,
    ) -> str:
        prompt = f"Введи {contact_label}. Например: `{example}`."
        if allow_clear:
            prompt = f"{prompt} Чтобы очистить поле, отправь `-`."
        return prompt

    @staticmethod
    def _build_profile_website_prompt() -> str:
        return (
            "Введи корректный website, например `https://company.com`. "
            "Чтобы очистить поле, отправь `-`."
        )
