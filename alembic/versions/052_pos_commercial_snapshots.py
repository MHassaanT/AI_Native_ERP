"""Apply shared price/UOM snapshots to POS lines.

Revision ID: 052_pos_commercial_snapshots
Revises: 051_product_bundle_snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "052_pos_commercial_snapshots"
down_revision = "051_product_bundle_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_invoices", sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_price_list", "pos_invoices", "price_lists", ["price_list_id"], ["price_list_id"])
    op.add_column("pos_invoice_items", sa.Column("uom_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_item_uom", "pos_invoice_items", "uoms", ["uom_id"], ["uom_id"])
    op.add_column("pos_invoice_items", sa.Column("conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("pos_invoice_items", sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.execute("UPDATE pos_invoice_items SET stock_quantity = quantity")
    op.add_column("pos_invoice_items", sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_item_price_list", "pos_invoice_items", "price_lists", ["price_list_id"], ["price_list_id"])
    op.add_column("pos_invoice_items", sa.Column("item_price_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_item_item_price", "pos_invoice_items", "item_prices", ["item_price_id"], ["item_price_id"])
    op.add_column("pos_invoice_items", sa.Column("price_list_rate", sa.Numeric(18, 4), nullable=True))
    op.add_column("pos_invoice_items", sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("pos_invoice_items", sa.Column("pricing_rule_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_item_pricing_rule", "pos_invoice_items", "pricing_rules", ["pricing_rule_id"], ["pricing_rule_id"])
    op.add_column("pos_invoice_items", sa.Column("promotion_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_invoice_item_promotion", "pos_invoice_items", "promotional_schemes", ["promotion_id"], ["scheme_id"])
    op.add_column("pos_invoice_items", sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("pos_invoice_items", "is_free")
    op.drop_constraint("fk_pos_invoice_item_promotion", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "promotion_id")
    op.drop_constraint("fk_pos_invoice_item_pricing_rule", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "pricing_rule_id")
    op.drop_column("pos_invoice_items", "discount_amount")
    op.drop_column("pos_invoice_items", "price_list_rate")
    op.drop_constraint("fk_pos_invoice_item_item_price", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "item_price_id")
    op.drop_constraint("fk_pos_invoice_item_price_list", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "price_list_id")
    op.drop_column("pos_invoice_items", "stock_quantity")
    op.drop_column("pos_invoice_items", "conversion_factor")
    op.drop_constraint("fk_pos_invoice_item_uom", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "uom_id")
    op.drop_constraint("fk_pos_invoice_price_list", "pos_invoices", type_="foreignkey")
    op.drop_column("pos_invoices", "price_list_id")
