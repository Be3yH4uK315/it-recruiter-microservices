from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    BIGINT,
    TEXT,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
)
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


class Candidate(Base):
    __tablename__ = "candidates"

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
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline_role: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    work_modes: Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contacts_visibility: Mapped[ContactsVisibility] = mapped_column(
        SQLAlchemyEnum(
            ContactsVisibility,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="contactsvisibility",
        ),
        default=ContactsVisibility.ON_REQUEST,
        server_default=ContactsVisibility.ON_REQUEST.value,
        nullable=False,
    )
    contacts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        SQLAlchemyEnum(
            CandidateStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="candidatestatus",
        ),
        default=CandidateStatus.ACTIVE,
        server_default=CandidateStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    english_level: Mapped[EnglishLevel | None] = mapped_column(
        SQLAlchemyEnum(
            EnglishLevel,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="englishlevel",
        ),
        nullable=True,
        index=True,
    )
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resume_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    skills: Mapped[list["CandidateSkill"]] = relationship(
        "CandidateSkill",
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    experiences: Mapped[list["Experience"]] = relationship(
        "Experience",
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    education: Mapped[list["Education"]] = relationship(
        "Education",
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __mapper_args__ = {"version_id_col": version_id}

    __table_args__ = (Index("ix_candidates_salary_range", "salary_min", "salary_max"),)


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[SkillKind] = mapped_column(
        SQLAlchemyEnum(
            SkillKind,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="skillkind",
        ),
        nullable=False,
    )
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="skills")

    __table_args__ = (Index("ix_candidate_skill_lookup", "skill", "kind"),)


class Education(Base):
    __tablename__ = "candidate_education"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(100), nullable=False)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="education")


class Experience(Base):
    __tablename__ = "candidate_experiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="experiences")


class Project(Base):
    __tablename__ = "candidate_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    links: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="projects")
