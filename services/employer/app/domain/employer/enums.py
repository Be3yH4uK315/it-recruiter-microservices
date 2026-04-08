from enum import StrEnum


class SearchStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class DecisionType(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    SKIP = "skip"


class ContactRequestStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"


class ContactsVisibility(StrEnum):
    PUBLIC = "public"
    ON_REQUEST = "on_request"
    HIDDEN = "hidden"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
