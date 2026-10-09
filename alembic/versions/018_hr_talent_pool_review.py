"""Stage likely email applicants in the talent pool for recruiter review.

Revision ID: 018_hr_talent_pool_review
Revises: 017_whatsapp_support_channel
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018_hr_talent_pool_review"
down_revision: str | None = "017_whatsapp_support_channel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_talent_pool_prospect_status",
        "candidate_talent_pool_prospects",
        type_="check",
    )
    op.create_check_constraint(
        "ck_talent_pool_prospect_status",
        "candidate_talent_pool_prospects",
        "status IN ('PENDING_REVIEW', 'POOLED', 'TRANSFERRED', 'DISMISSED')",
    )
    op.execute(
        sa.text(
            """
            INSERT INTO candidate_talent_pool_prospects (
                prospect_id,
                tenant_id,
                source_review_id,
                applicant_name,
                applicant_email,
                desired_role,
                profile_text,
                status
            )
            SELECT
                gen_random_uuid(),
                tenant_id,
                review_id,
                applicant_name,
                applicant_email,
                desired_role,
                resume_text,
                'PENDING_REVIEW'
            FROM recruitment_email_reviews
            WHERE status = 'REVIEW_REQUIRED'
            ON CONFLICT (source_review_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM candidate_talent_pool_prospects WHERE status = 'PENDING_REVIEW'"
        )
    )
    op.drop_constraint(
        "ck_talent_pool_prospect_status",
        "candidate_talent_pool_prospects",
        type_="check",
    )
    op.create_check_constraint(
        "ck_talent_pool_prospect_status",
        "candidate_talent_pool_prospects",
        "status IN ('POOLED', 'TRANSFERRED', 'DISMISSED')",
    )
