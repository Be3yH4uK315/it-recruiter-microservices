from __future__ import annotations


class ApplicationError(Exception):
    pass


class ValidationApplicationError(ApplicationError):
    pass


class IntegrationApplicationError(ApplicationError):
    pass
