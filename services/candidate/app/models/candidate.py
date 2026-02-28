import uuid
import enum
from sqlalchemy.orm import relationship
from sqlalchemy import (
    BIGINT, Column, String, Enum as SQLAlchemyEnum, DateTime, Text, func, 
    ForeignKey, Integer
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.db import Base

class EnglishLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class ContactsVisibility(str, enum.Enum):
    ON_REQUEST = "on_request"
    PUBLIC = "public"
    HIDDEN = "hidden"

class Status(str, enum.Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    BLOCKED = "blocked"

class SkillKind(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"
    TOOL = "tool"
    LANGUAGE = "language"

class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routing_key = Column(String(255), nullable=False)
    message_body = Column(JSONB, nullable=False)
    status = Column(String(50), default="pending", index=True, nullable=False) 
    retry_count = Column(Integer, default=0, nullable=False)
    error_log = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

class IdempotencyKey(Base):
    """
    Таблица для хранения ключей идемпотентности и результатов запросов.
    """
    __tablename__ = "idempotency_keys"
    
    key = Column(String(255), primary_key=True)
    response_body = Column(JSONB, nullable=True)
    status_code = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Education(Base):
    __tablename__ = "candidate_education"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    
    level = Column(String(100), nullable=False)
    institution = Column(String(255), nullable=False)
    year = Column(Integer, nullable=False)
    
    candidate = relationship("Candidate", back_populates="education")

class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)

    skill = Column(String(100), nullable=False)
    kind = Column(SQLAlchemyEnum(SkillKind), nullable=False)
    level = Column(Integer, nullable=True)
    
    candidate = relationship("Candidate", back_populates="skills")

class Project(Base):
    __tablename__ = "candidate_projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    links = Column(String(500), nullable=True)
    
    candidate = relationship("Candidate", back_populates="projects")

class Experience(Base):
    __tablename__ = "candidate_experiences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    
    company = Column(String(255), nullable=False)
    position = Column(String(255), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    responsibilities = Column(String, nullable=True)
    
    candidate = relationship("Candidate", back_populates="experiences")

class Avatar(Base):
    __tablename__ = "candidate_avatars"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    candidate = relationship("Candidate", back_populates="avatars")

class Resume(Base):
    __tablename__ = "candidate_resumes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    candidate = relationship("Candidate", back_populates="resumes")

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BIGINT, unique=True, nullable=False, index=True)
    
    display_name = Column(String(255))
    headline_role = Column(String(255))
    location = Column(String(255), nullable=True)
    work_modes = Column(JSONB, default=list)

    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    currency = Column(String(10), default="RUB")
    
    contacts_visibility = Column(SQLAlchemyEnum(ContactsVisibility), default=ContactsVisibility.ON_REQUEST, nullable=False)
    contacts = Column(JSONB)
    
    status = Column(SQLAlchemyEnum(Status), default=Status.ACTIVE, nullable=False, index=True)

    english_level = Column(SQLAlchemyEnum(EnglishLevel), nullable=True)
    about_me = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    version_id = Column(Integer, nullable=False, default=1)

    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")
    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")
    projects = relationship("Project", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")
    avatars = relationship("Avatar", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")
    education = relationship("Education", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin")

    __mapper_args__ = {
        "version_id_col": version_id
    }