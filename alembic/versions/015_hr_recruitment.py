"""Add tenant-scoped recruitment roles and candidate screening records.

Revision ID: 015_hr_recruitment
Revises: 014_remove_autonomous_workforce_and_hitl
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "015_hr_recruitment"
down_revision: str | None = "014_remove_autonomous_workforce_and_hitl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recruitment_roles",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="OPEN", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_recruitment_role_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id"),
        sa.UniqueConstraint("role_id", "tenant_id", name="uq_recruitment_role_tenant"),
    )
    op.create_index(
        "idx_recruitment_roles_tenant_status",
        "recruitment_roles",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index("ix_recruitment_roles_tenant_id", "recruitment_roles", ["tenant_id"])

    op.create_table(
        "candidate_applications",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicant_name", sa.String(length=128), nullable=True),
        sa.Column("applicant_email", sa.String(length=320), nullable=True),
        sa.Column("resume_filename", sa.String(length=255), nullable=False),
        sa.Column("resume_content_type", sa.String(length=128), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="READY", nullable=False),
        sa.Column("screening_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("screening_summary", sa.Text(), nullable=True),
        sa.Column(
            "matched_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("interview_email_subject", sa.String(length=998), nullable=True),
        sa.Column("interview_email_body", sa.Text(), nullable=True),
        sa.Column("evaluation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('READY', 'EVALUATED')",
            name="ck_candidate_application_status",
        ),
        sa.CheckConstraint(
            "screening_score IS NULL OR (screening_score >= 0 AND screening_score <= 100)",
            name="ck_candidate_application_score",
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="CASCADE",
            name="fk_candidate_application_role_tenant",
        ),
        sa.PrimaryKeyConstraint("application_id"),
    )
    op.create_index(
        "idx_candidate_applications_tenant_role",
        "candidate_applications",
        ["tenant_id", "role_id", "created_at"],
    )
    op.create_index(
        "idx_candidate_applications_tenant_score",
        "candidate_applications",
        ["tenant_id", "screening_score"],
    )
    op.create_index(
        "ix_candidate_applications_tenant_id",
        "candidate_applications",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_candidate_applications_tenant_score",
        table_name="candidate_applications",
    )
    op.drop_index(
        "ix_candidate_applications_tenant_id",
        table_name="candidate_applications",
    )
    op.drop_index(
        "idx_candidate_applications_tenant_role",
        table_name="candidate_applications",
    )
    op.drop_table("candidate_applications")
    op.drop_index(
        "idx_recruitment_roles_tenant_status",
        table_name="recruitment_roles",
    )
    op.drop_index("ix_recruitment_roles_tenant_id", table_name="recruitment_roles")
    op.drop_table("recruitment_roles")
