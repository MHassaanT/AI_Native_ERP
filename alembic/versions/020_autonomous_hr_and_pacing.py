"""Add autonomous HR email intake, candidate application notifications, and project pacing.

Revision ID: 020_autonomous_hr_and_pacing
Revises: 019_inventory_catalog
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "020_autonomous_hr_and_pacing"
down_revision: str | None = "019_inventory_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update candidate_applications with email ack and interview dispatch timestamps
    op.add_column(
        "candidate_applications",
        sa.Column("ack_email_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "candidate_applications",
        sa.Column("ack_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "candidate_applications",
        sa.Column("interview_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Update candidate_talent_pool_prospects with notification flags and allow nullable source_review_id
    op.add_column(
        "candidate_talent_pool_prospects",
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "candidate_talent_pool_prospects",
        sa.Column("notification_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "candidate_talent_pool_prospects",
        "source_review_id",
        nullable=True,
    )

    op.drop_constraint(
        "ck_recruitment_email_review_status",
        "recruitment_email_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recruitment_email_review_status",
        "recruitment_email_reviews",
        "status IN ('REVIEW_REQUIRED', 'APPLICATION_CREATED', 'ADDED_TO_POOL', "
        "'NOT_APPLICATION', 'PROJECT_UPDATE_RECORDED', 'DISMISSED')",
    )

    # 3. Update projects with last reminder sent timestamp and summary
    op.add_column(
        "projects",
        sa.Column("last_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("last_update_summary", sa.Text(), nullable=True),
    )

    # 4. Create hr_email_polling_state table for message deduplication
    op.create_table(
        "hr_email_polling_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_processed_message_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_talent_pool_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", name="uq_hr_email_polling_state_tenant"),
    )
    op.create_index("ix_hr_email_polling_state_tenant_id", "hr_email_polling_state", ["tenant_id"])

    # 5. Create project_updates table
    op.create_table(
        "project_updates",
        sa.Column("update_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("blockers", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_proj_updates_tenant_proj",
        "project_updates",
        ["tenant_id", "project_id", "created_at"],
    )
    op.create_index("ix_project_updates_tenant_id", "project_updates", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_project_updates_tenant_id", table_name="project_updates")
    op.drop_index("idx_proj_updates_tenant_proj", table_name="project_updates")
    op.drop_table("project_updates")

    op.drop_index("ix_hr_email_polling_state_tenant_id", table_name="hr_email_polling_state")
    op.drop_table("hr_email_polling_state")

    op.execute(
        sa.text(
            "UPDATE recruitment_email_reviews SET status = 'NOT_APPLICATION' "
            "WHERE status = 'PROJECT_UPDATE_RECORDED'"
        )
    )
    op.drop_constraint(
        "ck_recruitment_email_review_status",
        "recruitment_email_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recruitment_email_review_status",
        "recruitment_email_reviews",
        "status IN ('REVIEW_REQUIRED', 'APPLICATION_CREATED', 'ADDED_TO_POOL', "
        "'NOT_APPLICATION', 'DISMISSED')",
    )

    op.drop_column("projects", "last_update_summary")
    op.drop_column("projects", "last_reminder_sent_at")

    op.alter_column(
        "candidate_talent_pool_prospects",
        "source_review_id",
        nullable=False,
    )
    op.drop_column("candidate_talent_pool_prospects", "notification_sent_at")
    op.drop_column("candidate_talent_pool_prospects", "notification_sent")

    op.drop_column("candidate_applications", "interview_email_sent_at")
    op.drop_column("candidate_applications", "ack_email_sent_at")
    op.drop_column("candidate_applications", "ack_email_sent")
