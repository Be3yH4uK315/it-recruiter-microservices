"""add multi-role support

Revision ID: 0002_multi_role_auth
Revises: 0001_init_schema
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_multi_role_auth"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_auth_user_roles"),
    )
    op.create_index(
        "ix_auth_user_roles_role",
        "auth_user_roles",
        ["role"],
        unique=False,
    )

    op.execute("""
        INSERT INTO auth_user_roles (user_id, role, created_at)
        SELECT id, role, now()
        FROM auth_users
        """)


def downgrade() -> None:
    op.drop_index("ix_auth_user_roles_role", table_name="auth_user_roles")
    op.drop_table("auth_user_roles")
