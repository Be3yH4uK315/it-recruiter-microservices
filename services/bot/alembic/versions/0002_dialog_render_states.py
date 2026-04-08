"""add dialog render states

Revision ID: 0002_dialog_render_states
Revises: 0001_initial_bot_schema
Create Date: 2026-04-08 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_dialog_render_states"
down_revision = "0001_initial_bot_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dialog_render_states",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("primary_message_id", sa.Integer(), nullable=True),
        sa.Column("attachment_message_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("telegram_user_id"),
    )


def downgrade() -> None:
    op.drop_table("dialog_render_states")
