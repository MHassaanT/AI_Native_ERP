"""Preserve supplier quotation UOM and award provenance.

Revision ID: 050_supplier_quote_uom_provenance
Revises: 049_material_request_context
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "050_supplier_quote_uom_provenance"
down_revision = "049_material_request_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_quotation_items", sa.Column("uom_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("supplier_quotation_items", sa.Column("conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("supplier_quotation_items", sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.create_foreign_key("fk_supplier_quotation_item_uom", "supplier_quotation_items", "uoms", ["uom_id"], ["uom_id"])
    op.execute("UPDATE supplier_quotation_items SET stock_quantity = quantity")
    op.add_column("purchase_orders", sa.Column("supplier_quotation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_purchase_orders_supplier_quotation", "purchase_orders", "supplier_quotations", ["supplier_quotation_id"], ["sq_id"])


def downgrade() -> None:
    op.drop_constraint("fk_purchase_orders_supplier_quotation", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "supplier_quotation_id")
    op.drop_constraint("fk_supplier_quotation_item_uom", "supplier_quotation_items", type_="foreignkey")
    op.drop_column("supplier_quotation_items", "stock_quantity")
    op.drop_column("supplier_quotation_items", "conversion_factor")
    op.drop_column("supplier_quotation_items", "uom_id")
