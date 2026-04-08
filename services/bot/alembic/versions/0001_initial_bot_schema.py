"""initial bot schema

Revision ID: 0001_initial_bot_schema
Revises:
Create Date: 2026-03-28 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_bot_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_actors",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("language_code", sa.Text(), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("telegram_user_id"),
    )

    op.create_table(
        "bot_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_role", sa.String(length=32), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=32), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_authorized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bot_sessions_telegram_user_id", "bot_sessions", ["telegram_user_id"], unique=True
    )

    op.create_table(
        "conversation_states",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_context", sa.String(length=32), nullable=True),
        sa.Column("state_key", sa.String(length=128), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("telegram_user_id"),
    )

    op.create_table(
        "draft_payloads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("draft_type", sa.String(length=64), nullable=False),
        sa.Column("role_context", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_draft_payloads_telegram_user_id", "draft_payloads", ["telegram_user_id"], unique=False
    )

    op.create_table(
        "pending_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_context", sa.String(length=32), nullable=False),
        sa.Column("target_service", sa.String(length=32), nullable=False),
        sa.Column("target_kind", sa.String(length=64), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_file_id", sa.Text(), nullable=True),
        sa.Column("telegram_file_unique_id", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_uploads_telegram_user_id", "pending_uploads", ["telegram_user_id"], unique=False
    )

    op.create_table(
        "callback_contexts",
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_callback_contexts_telegram_user_id",
        "callback_contexts",
        ["telegram_user_id"],
        unique=False,
    )

    op.create_table(
        "processed_updates",
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("update_type", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="processing"),
        sa.PrimaryKeyConstraint("update_id"),
    )
    op.create_index(
        "ix_processed_updates_telegram_user_id",
        "processed_updates",
        ["telegram_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_processed_updates_telegram_user_id", table_name="processed_updates")
    op.drop_table("processed_updates")

    op.drop_index("ix_callback_contexts_telegram_user_id", table_name="callback_contexts")
    op.drop_table("callback_contexts")

    op.drop_index("ix_pending_uploads_telegram_user_id", table_name="pending_uploads")
    op.drop_table("pending_uploads")

    op.drop_index("ix_draft_payloads_telegram_user_id", table_name="draft_payloads")
    op.drop_table("draft_payloads")

    op.drop_table("conversation_states")

    op.drop_index("ix_bot_sessions_telegram_user_id", table_name="bot_sessions")
    op.drop_table("bot_sessions")

    op.drop_table("telegram_actors")
