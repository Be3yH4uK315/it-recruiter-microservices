from __future__ import annotations


class AuthDomainError(Exception):
    pass


class UserNotFoundError(AuthDomainError):
    pass


class UserAlreadyExistsError(AuthDomainError):
    pass


class UserInactiveError(AuthDomainError):
    pass


class InvalidTelegramAuthError(AuthDomainError):
    pass


class InvalidRefreshTokenError(AuthDomainError):
    pass


class InvalidAccessTokenError(AuthDomainError):
    pass


class RefreshSessionNotFoundError(AuthDomainError):
    pass


class RefreshSessionRevokedError(AuthDomainError):
    pass
