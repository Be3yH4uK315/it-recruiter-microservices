"""init_schema

Revision ID: f4d5b0024b5f
Revises:
Create Date: 2026-03-14 12:25:34.959281
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4d5b0024b5f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


search_status_enum = postgresql.ENUM(
    "active",
    "paused",
    "closed",
    name="searchstatus",
    create_type=False,
)

decision_type_enum = postgresql.ENUM(
    "like",
    "dislike",
    "skip",
    name="decisiontype",
    create_type=False,
)

contact_request_status_enum = postgresql.ENUM(
    "pending",
    "granted",
    "rejected",
    name="contactrequeststatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    search_status_enum.create(bind, checkfirst=True)
    decision_type_enum.create(bind, checkfirst=True)
    contact_request_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "employers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("company", sa.String(255)),
        sa.Column("contacts", postgresql.JSONB()),
        sa.Column("avatar_file_id", sa.UUID()),
        sa.Column("document_file_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_employers_telegram_id", "employers", ["telegram_id"], unique=True)

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_body", postgresql.JSONB()),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("routing_key", sa.String(255), nullable=False),
        sa.Column("message_body", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("error_log", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_outbox_status_created",
        "outbox_messages",
        ["status", "created_at"],
    )

    op.create_table(
        "search_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("employer_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column("search_offset", sa.Integer(), server_default="0"),
        sa.Column("search_total", sa.Integer(), server_default="0"),
        sa.Column(
            "status",
            search_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["employer_id"], ["employers.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_search_sessions_employer_id",
        "search_sessions",
        ["employer_id"],
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column(
            "decision",
            decision_type_enum,
            nullable=False,
        ),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["search_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "candidate_id", name="uq_decision_session_candidate"),
    )
    op.create_index("ix_decisions_candidate_id", "decisions", ["candidate_id"])
    op.create_index("ix_decisions_session_id", "decisions", ["session_id"])

    op.create_table(
        "search_session_candidates",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("headline_role", sa.String(255), nullable=False),
        sa.Column("experience_years", sa.Float(), server_default="0"),
        sa.Column("location", sa.String(255)),
        sa.Column("skills", postgresql.JSONB()),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("currency", sa.String(16)),
        sa.Column("english_level", sa.String(16)),
        sa.Column("about_me", sa.Text()),
        sa.Column("match_score", sa.Float(), server_default="0"),
        sa.Column("explanation", postgresql.JSONB()),
        sa.Column("is_consumed", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["search_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "candidate_id", name="uq_search_session_candidate"),
    )
    op.create_index(
        "ix_search_session_candidates_session_id",
        "search_session_candidates",
        ["session_id"],
    )
    op.create_index(
        "ix_search_session_candidates_candidate_id",
        "search_session_candidates",
        ["candidate_id"],
    )
    op.create_index(
        "ix_search_session_candidates_session_consumed_rank",
        "search_session_candidates",
        ["session_id", "is_consumed", "rank_position"],
    )

    op.create_table(
        "contact_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("employer_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            contact_request_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["employer_id"], ["employers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "employer_id",
            "candidate_id",
            name="uq_contact_request_employer_candidate",
        ),
    )
    op.create_index("ix_contacts_requests_employer_id", "contact_requests", ["employer_id"])
    op.create_index("ix_contacts_requests_candidate_id", "contact_requests", ["candidate_id"])
    op.create_index(
        "ix_contact_requests_employer_status",
        "contact_requests",
        ["employer_id", "status"],
    )
    op.create_index(
        "ix_contact_requests_candidate_status",
        "contact_requests",
        ["candidate_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_requests_candidate_status", table_name="contact_requests")
    op.drop_index("ix_contact_requests_employer_status", table_name="contact_requests")
    op.drop_index("ix_contacts_requests_candidate_id", table_name="contact_requests")
    op.drop_index("ix_contacts_requests_employer_id", table_name="contact_requests")

    op.drop_index(
        "ix_search_session_candidates_session_consumed_rank",
        table_name="search_session_candidates",
    )
    op.drop_index(
        "ix_search_session_candidates_candidate_id", table_name="search_session_candidates"
    )
    op.drop_index("ix_search_session_candidates_session_id", table_name="search_session_candidates")

    op.drop_index("ix_decisions_candidate_id", table_name="decisions")
    op.drop_index("ix_decisions_session_id", table_name="decisions")
    op.drop_index("ix_search_sessions_employer_id", table_name="search_sessions")
    op.drop_index("ix_outbox_status_created", table_name="outbox_messages")
    op.drop_index("ix_employers_telegram_id", table_name="employers")

    op.drop_table("contact_requests")
    op.drop_table("search_session_candidates")
    op.drop_table("decisions")
    op.drop_table("search_sessions")
    op.drop_table("outbox_messages")
    op.drop_table("idempotency_keys")
    op.drop_table("employers")

    bind = op.get_bind()

    contact_request_status_enum.drop(bind, checkfirst=True)
    decision_type_enum.drop(bind, checkfirst=True)
    search_status_enum.drop(bind, checkfirst=True)
