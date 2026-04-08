from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    CANDIDATE = "candidate"
    EMPLOYER = "employer"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    BOT = "bot"
    TELEGRAM = "telegram"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
