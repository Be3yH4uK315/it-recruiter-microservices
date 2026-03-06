import enum
import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    EMPLOYER = "employer"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    role = Column(SQLAlchemyEnum(UserRole), default=UserRole.CANDIDATE, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")
