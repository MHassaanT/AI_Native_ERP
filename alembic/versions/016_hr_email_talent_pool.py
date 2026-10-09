"""Add recruiter-reviewed Gmail intake and a tenant talent pool.

Revision ID: 016_hr_email_pool
Revises: 015_hr_recruitment
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "016_hr_email_pool"
down_revision: str | None = "015_hr_recruitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    inbound_unique_keys = inspector.get_unique_constraints("inbound_email_records")
    if not any(
        set(constraint["column_names"]) == {"message_id", "tenant_id"}
        for constraint in inbound_unique_keys
    ):
        op.create_unique_constraint(
            "uq_inbound_email_message_tenant",
            "inbound_email_records",
            ["message_id", "tenant_id"],
        )
    op.create_table(
        "recruitment_email_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inbound_message_id", sa.String(length=64), nullable=False),
        sa.Column("applicant_name", sa.String(length=128), nullable=True),
        sa.Column("applicant_email", sa.String(length=320), nullable=True),
        sa.Column("desired_role", sa.String(length=255), nullable=True),
        sa.Column("suggested_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="REVIEW_REQUIRED",
            nullable=False,
        ),
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
            "status IN ('REVIEW_REQUIRED', 'APPLICATION_CREATED', 'ADDED_TO_POOL', 'NOT_APPLICATION', 'DISMISSED')",
            name="ck_recruitment_email_review_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_recruitment_email_review_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["inbound_message_id", "tenant_id"],
            ["inbound_email_records.message_id", "inbound_email_records.tenant_id"],
            ondelete="CASCADE",
            name="fk_recruitment_email_review_inbound_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["suggested_role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="SET NULL (suggested_role_id)",
            name="fk_recruitment_email_review_role_tenant",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("review_id", "tenant_id", name="uq_recruitment_email_review_tenant"),
        sa.UniqueConstraint(
            "tenant_id", "inbound_message_id", name="uq_recruitment_email_review_message"
        ),
    )
    op.create_index(
        "idx_recruitment_email_review_queue",
        "recruitment_email_reviews",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_recruitment_email_reviews_tenant_id",
        "recruitment_email_reviews",
        ["tenant_id"],
    )

    candidate_application_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("candidate_applications")
    }
    if "source_review_id" not in candidate_application_columns:
        op.add_column(
            "candidate_applications",
            sa.Column("source_review_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    candidate_application_foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(
        "candidate_applications"
    )
    if not any(
        foreign_key.get("referred_table") == "recruitment_email_reviews"
        and set(foreign_key.get("constrained_columns", []))
        == {"source_review_id", "tenant_id"}
        and set(foreign_key.get("referred_columns", [])) == {"review_id", "tenant_id"}
        for foreign_key in candidate_application_foreign_keys
    ):
        op.create_foreign_key(
            "fk_candidate_application_review_tenant",
            "candidate_applications",
            "recruitment_email_reviews",
            ["source_review_id", "tenant_id"],
            ["review_id", "tenant_id"],
            ondelete="SET NULL (source_review_id)",
        )
    candidate_application_unique_keys = sa.inspect(op.get_bind()).get_unique_constraints(
        "candidate_applications"
    )
    if not any(
        constraint.get("name") == "uq_candidate_application_source_review"
        or set(constraint["column_names"]) == {"source_review_id"}
        for constraint in candidate_application_unique_keys
    ):
        op.create_unique_constraint(
            "uq_candidate_application_source_review",
            "candidate_applications",
            ["source_review_id"],
        )

    op.create_table(
        "candidate_talent_pool_prospects",
        sa.Column("prospect_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicant_name", sa.String(length=128), nullable=True),
        sa.Column("applicant_email", sa.String(length=320), nullable=True),
        sa.Column("desired_role", sa.String(length=255), nullable=True),
        sa.Column("profile_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="POOLED", nullable=False),
        sa.Column("matched_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("match_summary", sa.Text(), nullable=True),
        sa.Column(
            "match_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('POOLED', 'TRANSFERRED', 'DISMISSED')",
            name="ck_talent_pool_prospect_status",
        ),
        sa.CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="ck_talent_pool_match_score",
        ),
        sa.ForeignKeyConstraint(
            ["matched_role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="SET NULL (matched_role_id)",
            name="fk_talent_pool_role_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["source_review_id", "tenant_id"],
            ["recruitment_email_reviews.review_id", "recruitment_email_reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_talent_pool_review_tenant",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("prospect_id"),
        sa.UniqueConstraint("source_review_id", name="uq_talent_pool_source_review"),
    )
    op.create_index(
        "idx_talent_pool_tenant_status",
        "candidate_talent_pool_prospects",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_candidate_talent_pool_prospects_tenant_id",
        "candidate_talent_pool_prospects",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_talent_pool_tenant_status",
        table_name="candidate_talent_pool_prospects",
    )
    op.drop_index(
        "ix_candidate_talent_pool_prospects_tenant_id",
        table_name="candidate_talent_pool_prospects",
    )
    op.drop_table("candidate_talent_pool_prospects")
    op.drop_constraint(
        "uq_candidate_application_source_review",
        "candidate_applications",
        type_="unique",
    )
    op.drop_constraint(
        "fk_candidate_application_review_tenant",
        "candidate_applications",
        type_="foreignkey",
    )
    op.drop_column("candidate_applications", "source_review_id")
    op.drop_index(
        "idx_recruitment_email_review_queue",
        table_name="recruitment_email_reviews",
    )
    op.drop_index(
        "ix_recruitment_email_reviews_tenant_id",
        table_name="recruitment_email_reviews",
    )
    op.drop_table("recruitment_email_reviews")
    op.drop_constraint(
        "uq_inbound_email_message_tenant",
        "inbound_email_records",
        type_="unique",
    )
