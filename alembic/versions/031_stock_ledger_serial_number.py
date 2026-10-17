"""Add serial number tracking to stock ledger entries.

Revision ID: 031_stock_ledger_serial_number
Revises: 030_pos_invoice_return_fields
"""

from collections.abc import Sequence

from alembic import op

revision: str = "031_stock_ledger_serial_number"
down_revision: str | None = "030_pos_invoice_return_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE stock_ledger_entries ADD COLUMN IF NOT EXISTS serial_no VARCHAR(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE stock_ledger_entries DROP COLUMN IF EXISTS serial_no")
