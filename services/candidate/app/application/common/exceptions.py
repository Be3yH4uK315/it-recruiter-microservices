from __future__ import annotations


class ApplicationError(Exception):
    pass


class AccessDeniedError(ApplicationError):
    pass


class ValidationApplicationError(ApplicationError):
    pass


class IntegrationUnavailableError(ApplicationError):
    pass
