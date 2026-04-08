from __future__ import annotations

import uuid

from sqlalchemy import (
    BIGINT,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.employer.enums import ContactRequestStatus, DecisionType, SearchStatus
from app.infrastructure.db.base import Base


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    routing_key: Mapped[str] = mapped_column(String(255), nullable=False)
    message_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    processed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (Index("ix_outbox_status_created", "status", "created_at"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class EmployerModel(Base):
    __tablename__ = "employers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    telegram_id: Mapped[int] = mapped_column(
        BIGINT,
        unique=True,
        index=True,
        nullable=False,
    )
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contacts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    document_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    search_sessions: Mapped[list["SearchSessionModel"]] = relationship(
        "SearchSessionModel",
        back_populates="employer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    contact_requests: Mapped[list["ContactRequestModel"]] = relationship(
        "ContactRequestModel",
        back_populates="employer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SearchSessionModel(Base):
    __tablename__ = "search_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    search_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    search_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[SearchStatus] = mapped_column(
        SQLAlchemyEnum(
            SearchStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="searchstatus",
        ),
        default=SearchStatus.ACTIVE,
        server_default=SearchStatus.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    employer: Mapped["EmployerModel"] = relationship(
        "EmployerModel",
        back_populates="search_sessions",
    )
    decisions: Mapped[list["DecisionModel"]] = relationship(
        "DecisionModel",
        back_populates="search_session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pool_items: Mapped[list["SearchSessionCandidateModel"]] = relationship(
        "SearchSessionCandidateModel",
        back_populates="search_session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SearchSessionCandidateModel.rank_position.asc()",
    )


class SearchSessionCandidateModel(Base):
    __tablename__ = "search_session_candidates"
    __table_args__ = (
        UniqueConstraint("session_id", "candidate_id", name="uq_search_session_candidate"),
        Index(
            "ix_search_session_candidates_session_consumed_rank",
            "session_id",
            "is_consumed",
            "rank_position",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline_role: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_years: Mapped[float] = mapped_column(nullable=False, default=0.0)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[dict] | list[str] | None] = mapped_column(JSONB, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    english_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    search_session: Mapped["SearchSessionModel"] = relationship(
        "SearchSessionModel",
        back_populates="pool_items",
    )


class DecisionModel(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("session_id", "candidate_id", name="uq_decision_session_candidate"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    decision: Mapped[DecisionType] = mapped_column(
        SQLAlchemyEnum(
            DecisionType,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="decisiontype",
        ),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    search_session: Mapped["SearchSessionModel"] = relationship(
        "SearchSessionModel",
        back_populates="decisions",
    )


class ContactRequestModel(Base):
    __tablename__ = "contact_requests"
    __table_args__ = (
        UniqueConstraint(
            "employer_id",
            "candidate_id",
            name="uq_contact_request_employer_candidate",
        ),
        Index("ix_contact_requests_employer_status", "employer_id", "status"),
        Index("ix_contact_requests_candidate_status", "candidate_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[ContactRequestStatus] = mapped_column(
        SQLAlchemyEnum(
            ContactRequestStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="contactrequeststatus",
        ),
        nullable=False,
        default=ContactRequestStatus.PENDING,
        server_default=ContactRequestStatus.PENDING.value,
        index=True,
    )
    responded_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    employer: Mapped["EmployerModel"] = relationship(
        "EmployerModel",
        back_populates="contact_requests",
    )
