from __future__ import annotations

from enum import StrEnum


class EnglishLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ContactsVisibility(StrEnum):
    ON_REQUEST = "on_request"
    PUBLIC = "public"
    HIDDEN = "hidden"


class CandidateStatus(StrEnum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    BLOCKED = "blocked"


class SkillKind(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    TOOL = "tool"
    LANGUAGE = "language"


class WorkMode(StrEnum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"
