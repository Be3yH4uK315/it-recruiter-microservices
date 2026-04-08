from __future__ import annotations


class EmployerDomainError(Exception):
    pass


class EmployerAlreadyExistsError(EmployerDomainError):
    pass


class EmployerNotFoundError(EmployerDomainError):
    pass


class SearchSessionNotFoundError(EmployerDomainError):
    pass


class SearchSessionClosedError(EmployerDomainError):
    pass


class SearchSessionPausedError(EmployerDomainError):
    pass


class InvalidSearchFilterError(EmployerDomainError):
    pass


class ContactRequestError(EmployerDomainError):
    pass


class ContactRequestNotFoundError(ContactRequestError):
    pass


class ContactRequestForbiddenError(ContactRequestError):
    pass


class ContactRequestAlreadyResolvedError(ContactRequestError):
    pass


class DuplicateDecisionError(EmployerDomainError):
    pass


class InvalidEmployerFileError(EmployerDomainError):
    pass
