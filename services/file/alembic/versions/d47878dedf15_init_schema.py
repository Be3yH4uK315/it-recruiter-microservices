"""init schema

Revision ID: d47878dedf15
Revises:
Create Date: 2026-03-15 10:20:59.443409
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d47878dedf15"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


file_category_enum = postgresql.ENUM(
    "candidate_avatar",
    "candidate_resume",
    "employer_avatar",
    "employer_document",
    name="filecategory",
    create_type=False,
)

file_status_enum = postgresql.ENUM(
    "pending_upload",
    "active",
    "deleted",
    name="filestatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    file_category_enum.create(bind, checkfirst=True)
    file_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_service", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("category", file_category_enum, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            file_status_enum,
            nullable=False,
            server_default="pending_upload",
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(op.f("ix_files_category"), "files", ["category"], unique=False)
    op.create_index(
        "ix_files_owner_category_status",
        "files",
        ["owner_service", "owner_id", "category", "status"],
        unique=False,
    )
    op.create_index(op.f("ix_files_owner_id"), "files", ["owner_id"], unique=False)
    op.create_index("ix_files_owner_lookup", "files", ["owner_service", "owner_id"], unique=False)
    op.create_index(op.f("ix_files_owner_service"), "files", ["owner_service"], unique=False)
    op.create_index(op.f("ix_files_status"), "files", ["status"], unique=False)
    op.create_index("ix_files_status_created", "files", ["status", "created_at"], unique=False)

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column("message_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_log", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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


def downgrade() -> None:
    op.drop_index("ix_outbox_status_created", table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_table("idempotency_keys")

    op.drop_index("ix_files_status_created", table_name="files")
    op.drop_index(op.f("ix_files_status"), table_name="files")
    op.drop_index(op.f("ix_files_owner_service"), table_name="files")
    op.drop_index("ix_files_owner_lookup", table_name="files")
    op.drop_index(op.f("ix_files_owner_id"), table_name="files")
    op.drop_index("ix_files_owner_category_status", table_name="files")
    op.drop_index(op.f("ix_files_category"), table_name="files")
    op.drop_table("files")

    op.execute("DROP TYPE IF EXISTS filecategory")
    op.execute("DROP TYPE IF EXISTS filestatus")
