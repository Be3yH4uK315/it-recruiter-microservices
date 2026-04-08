from __future__ import annotations


class FileDomainError(Exception):
    pass


class FileNotFoundError(FileDomainError):
    pass


class FileAlreadyDeletedError(FileDomainError):
    pass


class FileAccessDeniedError(FileDomainError):
    pass


class InvalidFileCategoryError(FileDomainError):
    pass


class InvalidFileStateError(FileDomainError):
    pass
