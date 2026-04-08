"""init schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-03-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_id", sa.BIGINT(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_users_telegram_id", "auth_users", ["telegram_id"], unique=True)
    op.create_index("ix_auth_users_role", "auth_users", ["role"], unique=False)

    op.create_table(
        "auth_refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_refresh_sessions_user_id",
        "auth_refresh_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_auth_refresh_sessions_token_hash",
        "auth_refresh_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_refresh_sessions_expires_at",
        "auth_refresh_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_refresh_sessions_revoked",
        "auth_refresh_sessions",
        ["revoked"],
        unique=False,
    )
    op.create_index(
        "ix_auth_refresh_sessions_user_created",
        "auth_refresh_sessions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_refresh_sessions_user_revoked_expires",
        "auth_refresh_sessions",
        ["user_id", "revoked", "expires_at"],
        unique=False,
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column("message_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_log", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_status_created",
        "outbox_messages",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")

    op.drop_index("ix_outbox_status_created", table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_index(
        "ix_auth_refresh_sessions_user_revoked_expires",
        table_name="auth_refresh_sessions",
    )
    op.drop_index("ix_auth_refresh_sessions_user_created", table_name="auth_refresh_sessions")
    op.drop_index("ix_auth_refresh_sessions_revoked", table_name="auth_refresh_sessions")
    op.drop_index("ix_auth_refresh_sessions_expires_at", table_name="auth_refresh_sessions")
    op.drop_index("ix_auth_refresh_sessions_token_hash", table_name="auth_refresh_sessions")
    op.drop_index("ix_auth_refresh_sessions_user_id", table_name="auth_refresh_sessions")
    op.drop_table("auth_refresh_sessions")

    op.drop_index("ix_auth_users_role", table_name="auth_users")
    op.drop_index("ix_auth_users_telegram_id", table_name="auth_users")
    op.drop_table("auth_users")
