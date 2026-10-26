"""Link customer credit-note return lines to their source sales-invoice lines.

Revision ID: 046_credit_note_sales_invoice_lineage
Revises: 045_supplier_invoice_tax_snapshots
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "046_credit_note_sales_invoice_lineage"
down_revision: str | None = "045_supplier_invoice_tax_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "credit_note_items",
        sa.Column("sales_invoice_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_credit_note_item_sales_invoice_item",
        "credit_note_items", "sales_invoice_items",
        ["sales_invoice_item_id"], ["invoice_item_id"],
    )
    op.create_index(
        "ix_credit_note_item_tenant_sales_invoice_item",
        "credit_note_items", ["tenant_id", "sales_invoice_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_note_item_tenant_sales_invoice_item", table_name="credit_note_items")
    op.drop_constraint("fk_credit_note_item_sales_invoice_item", "credit_note_items", type_="foreignkey")
    op.drop_column("credit_note_items", "sales_invoice_item_id")
