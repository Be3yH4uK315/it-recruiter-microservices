"""init schema

Revision ID: 54067cc9a3a7
Revises:
Create Date: 2026-03-13 15:51:34.313737
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "54067cc9a3a7"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


contacts_visibility_enum = postgresql.ENUM(
    "on_request",
    "public",
    "hidden",
    name="contactsvisibility",
    create_type=False,
)

candidate_status_enum = postgresql.ENUM(
    "active",
    "hidden",
    "blocked",
    name="candidatestatus",
    create_type=False,
)

english_level_enum = postgresql.ENUM(
    "A1",
    "A2",
    "B1",
    "B2",
    "C1",
    "C2",
    name="englishlevel",
    create_type=False,
)

skill_kind_enum = postgresql.ENUM(
    "hard",
    "soft",
    "tool",
    "language",
    name="skillkind",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    contacts_visibility_enum.create(bind, checkfirst=True)
    candidate_status_enum.create(bind, checkfirst=True)
    english_level_enum.create(bind, checkfirst=True)
    skill_kind_enum.create(bind, checkfirst=True)

    op.create_table(
        "candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("telegram_id", sa.BIGINT(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("headline_role", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("work_modes", sa.ARRAY(sa.TEXT()), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column(
            "contacts_visibility",
            contacts_visibility_enum,
            nullable=False,
            server_default="on_request",
        ),
        sa.Column("contacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", candidate_status_enum, nullable=False, server_default="active"),
        sa.Column("english_level", english_level_enum, nullable=True),
        sa.Column("about_me", sa.Text(), nullable=True),
        sa.Column("avatar_file_id", sa.UUID(), nullable=True),
        sa.Column("resume_file_id", sa.UUID(), nullable=True),
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
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidates_telegram_id"), "candidates", ["telegram_id"], unique=True)
    op.create_index(
        op.f("ix_candidates_headline_role"), "candidates", ["headline_role"], unique=False
    )
    op.create_index(op.f("ix_candidates_location"), "candidates", ["location"], unique=False)
    op.create_index(op.f("ix_candidates_status"), "candidates", ["status"], unique=False)
    op.create_index(
        op.f("ix_candidates_english_level"), "candidates", ["english_level"], unique=False
    )
    op.create_index(
        "ix_candidates_salary_range", "candidates", ["salary_min", "salary_max"], unique=False
    )

    op.create_table(
        "candidate_skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("skill", sa.String(length=100), nullable=False),
        sa.Column("kind", skill_kind_enum, nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_skills_candidate_id"), "candidate_skills", ["candidate_id"], unique=False
    )
    op.create_index(
        "ix_candidate_skill_lookup", "candidate_skills", ["skill", "kind"], unique=False
    )

    op.create_table(
        "candidate_education",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.String(length=100), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_education_candidate_id"),
        "candidate_education",
        ["candidate_id"],
        unique=False,
    )

    op.create_table(
        "candidate_experiences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_experiences_candidate_id"),
        "candidate_experiences",
        ["candidate_id"],
        unique=False,
    )

    op.create_table(
        "candidate_projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_projects_candidate_id"),
        "candidate_projects",
        ["candidate_id"],
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
        sa.Column("error_log", sa.Text(), nullable=True),
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

    op.drop_index(op.f("ix_candidate_projects_candidate_id"), table_name="candidate_projects")
    op.drop_table("candidate_projects")

    op.drop_index(op.f("ix_candidate_experiences_candidate_id"), table_name="candidate_experiences")
    op.drop_table("candidate_experiences")

    op.drop_index(op.f("ix_candidate_education_candidate_id"), table_name="candidate_education")
    op.drop_table("candidate_education")

    op.drop_index(op.f("ix_candidate_skills_candidate_id"), table_name="candidate_skills")
    op.drop_index("ix_candidate_skill_lookup", table_name="candidate_skills")
    op.drop_table("candidate_skills")

    op.drop_index("ix_candidates_salary_range", table_name="candidates")
    op.drop_index(op.f("ix_candidates_english_level"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_status"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_location"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_headline_role"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_telegram_id"), table_name="candidates")
    op.drop_table("candidates")

    op.execute("DROP TYPE IF EXISTS skillkind")
    op.execute("DROP TYPE IF EXISTS englishlevel")
    op.execute("DROP TYPE IF EXISTS candidatestatus")
    op.execute("DROP TYPE IF EXISTS contactsvisibility")
