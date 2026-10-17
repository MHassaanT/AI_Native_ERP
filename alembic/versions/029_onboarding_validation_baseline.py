"""Exclude setup and demo records from new-tenant onboarding completion.

Revision ID: 029_onboarding_validation_baseline
Revises: 028_workstation_operating_fields
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "029_onboarding_validation_baseline"
down_revision: str | None = "028_workstation_operating_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "onboarding_steps",
        sa.Column("validation_baseline_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("onboarding_steps", "validation_baseline_at")
