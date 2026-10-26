"""Store supplier invoice tax source and calculation snapshot.

Revision ID: 045_supplier_invoice_tax_snapshots
Revises: 044_goods_receipt_warehouse_inspection
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "045_supplier_invoice_tax_snapshots"
down_revision: str | None = "044_goods_receipt_warehouse_inspection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("supplier_invoices", sa.Column("purchase_tax_template_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("supplier_invoices", sa.Column("tax_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(
        "fk_supplier_invoice_purchase_tax_template", "supplier_invoices",
        "purchase_taxes_and_charges_templates", ["purchase_tax_template_id"], ["template_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_supplier_invoice_purchase_tax_template", "supplier_invoices", type_="foreignkey")
    op.drop_column("supplier_invoices", "tax_snapshot")
    op.drop_column("supplier_invoices", "purchase_tax_template_id")
