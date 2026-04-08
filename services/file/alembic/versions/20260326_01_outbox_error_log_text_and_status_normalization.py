"""normalize outbox status values and widen error_log to text

Revision ID: 20260326_01_outbox_normalization
Revises: d47878dedf15
Create Date: 2026-03-26 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260326_01_outbox_normalization"
down_revision = "d47878dedf15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE outbox_messages
        SET status = 'published'
        WHERE status = 'processed'
        """)

    op.alter_column(
        "outbox_messages",
        "error_log",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "outbox_messages",
        "error_log",
        existing_type=sa.Text(),
        type_=sa.String(),
        existing_nullable=True,
    )

    op.execute("""
        UPDATE outbox_messages
        SET status = 'processed'
        WHERE status = 'published'
        """)
