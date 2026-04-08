from __future__ import annotations


class CandidateDomainError(Exception):
    pass


class CandidateNotFoundError(CandidateDomainError):
    pass


class CandidateAlreadyExistsError(CandidateDomainError):
    pass


class CandidateBlockedError(CandidateDomainError):
    pass


class CannotUnblockYourselfError(CandidateDomainError):
    pass


class ResumeNotFoundError(CandidateDomainError):
    pass


class AvatarNotFoundError(CandidateDomainError):
    pass


class InvalidSalaryRangeError(CandidateDomainError):
    pass


class InvalidCandidateFileError(CandidateDomainError):
    pass


class IntegrationUnavailableError(CandidateDomainError):
    pass
