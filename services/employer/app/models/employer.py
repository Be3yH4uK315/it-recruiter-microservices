import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from app.core.db import Base


class DecisionType(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    SKIP = "skip"


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("search_sessions.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    decision = Column(SQLAlchemyEnum(DecisionType), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    search_session = relationship("SearchSession", back_populates="decisions")

    __table_args__ = (UniqueConstraint("session_id", "candidate_id", name="_session_candidate_uc"),)


class ContactsRequest(Base):
    __tablename__ = "contacts_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    granted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    employer = relationship("Employer", back_populates="contact_requests")


class Employer(Base):
    __tablename__ = "employers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BIGINT, unique=True, index=True, nullable=False)
    company = Column(String(255), nullable=True)
    contacts = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    search_sessions = relationship(
        "SearchSession", back_populates="employer", cascade="all, delete-orphan"
    )
    contact_requests = relationship(
        "ContactsRequest", back_populates="employer", cascade="all, delete-orphan"
    )


class SearchStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False)
    title = Column(String(255), nullable=False)
    filters = Column(JSONB, nullable=False)
    status = Column(SQLAlchemyEnum(SearchStatus), default=SearchStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    employer = relationship("Employer", back_populates="search_sessions")
    decisions = relationship(
        "Decision", back_populates="search_session", cascade="all, delete-orphan"
    )
