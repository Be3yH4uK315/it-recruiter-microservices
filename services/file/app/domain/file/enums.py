from __future__ import annotations

from enum import StrEnum


class FileCategory(StrEnum):
    CANDIDATE_AVATAR = "candidate_avatar"
    CANDIDATE_RESUME = "candidate_resume"
    EMPLOYER_AVATAR = "employer_avatar"
    EMPLOYER_DOCUMENT = "employer_document"


class FileStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    ACTIVE = "active"
    DELETED = "deleted"
