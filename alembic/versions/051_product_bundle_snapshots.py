"""Store immutable product-bundle component snapshots on selling documents.

Revision ID: 051_product_bundle_snapshots
Revises: 050_supplier_quote_uom_provenance
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "051_product_bundle_snapshots"
down_revision = "050_supplier_quote_uom_provenance"
branch_labels = None
depends_on = None


TABLES = (
    "sales_quotation_items",
    "sales_order_items",
    "delivery_note_items",
    "sales_invoice_items",
    "credit_note_items",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("bundle_components_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_column(table, "bundle_components_snapshot")
