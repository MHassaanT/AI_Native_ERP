"""Add POS invoice return and consolidation fields missing from the original schema.

Revision ID: 030_pos_invoice_return_fields
Revises: 029_onboarding_validation_baseline
"""

from collections.abc import Sequence

from alembic import op

revision: str = "030_pos_invoice_return_fields"
down_revision: str | None = "029_onboarding_validation_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this safe for environments where ORM table synchronization
    # or a manual hotfix already introduced one or more fields.
    op.execute("ALTER TABLE pos_invoices ADD COLUMN IF NOT EXISTS is_return BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE pos_invoices ADD COLUMN IF NOT EXISTS return_against VARCHAR(64)")
    op.execute("ALTER TABLE pos_invoices ADD COLUMN IF NOT EXISTS consolidated_invoice_id UUID")


def downgrade() -> None:
    op.execute("ALTER TABLE pos_invoices DROP COLUMN IF EXISTS consolidated_invoice_id")
    op.execute("ALTER TABLE pos_invoices DROP COLUMN IF EXISTS return_against")
    op.execute("ALTER TABLE pos_invoices DROP COLUMN IF EXISTS is_return")
