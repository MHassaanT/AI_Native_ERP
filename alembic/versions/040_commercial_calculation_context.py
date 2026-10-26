"""Add price UOM context and deterministic promotion/rule configuration.

Revision ID: 040_commercial_calculation_context
Revises: 039_document_lineage_and_snapshots
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "040_commercial_calculation_context"
down_revision: str | None = "039_document_lineage_and_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("weight_per_unit", sa.Numeric(18, 8), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("weight_uom", sa.String(length=16), nullable=False, server_default="KG"))
    op.create_check_constraint("ck_item_weight_nonnegative", "items", "weight_per_unit >= 0")
    op.add_column("item_prices", sa.Column("uom_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("item_prices", sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("item_prices", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key("fk_item_price_uom", "item_prices", "uoms", ["uom_id"], ["uom_id"])
    op.drop_constraint("uq_item_price_period", "item_prices", type_="unique")
    op.create_unique_constraint(
        "uq_item_price_period", "item_prices",
        ["tenant_id", "item_id", "price_list_id", "uom_id", "currency", "valid_from"],
    )
    op.create_check_constraint("ck_item_price_priority_nonnegative", "item_prices", "priority >= 0")
    op.add_column("product_bundle_items", sa.Column("uom_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_product_bundle_item_uom", "product_bundle_items", "uoms", ["uom_id"], ["uom_id"])
    op.add_column("promotional_schemes", sa.Column("free_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_promo_free_item", "promotional_schemes", "items", ["free_item_id"], ["item_id"])
    op.create_check_constraint(
        "ck_promo_free_item_required", "promotional_schemes",
        "scheme_type <> 'BUY_X_GET_Y' OR free_item_id IS NOT NULL",
    )
    op.add_column("pricing_rules", sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.false()))
    for table in ("purchase_orders", "sales_orders"):
        op.add_column(table, sa.Column("shipping_charge", sa.Numeric(18, 4), nullable=False, server_default="0"))
        op.add_column(table, sa.Column("calculation_hash", sa.String(length=64), nullable=True))
        op.create_check_constraint(f"ck_{table}_shipping_nonnegative", table, "shipping_charge >= 0")
    for table in ("purchase_order_items", "sales_quotation_items", "sales_order_items"):
        op.add_column(table, sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"))
        op.add_column(table, sa.Column("pricing_rule_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("promotion_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_check_constraint(f"ck_{table}_discount_nonnegative", table, "discount_amount >= 0")
        op.create_foreign_key(f"fk_{table}_pricing_rule", table, "pricing_rules", ["pricing_rule_id"], ["pricing_rule_id"])
        op.create_foreign_key(f"fk_{table}_promotion", table, "promotional_schemes", ["promotion_id"], ["scheme_id"])
        op.create_index(f"ix_{table}_tenant_rule", table, ["tenant_id", "pricing_rule_id"])
        op.create_index(f"ix_{table}_tenant_promotion", table, ["tenant_id", "promotion_id"])
    for table in ("supplier_invoice_items", "sales_invoice_items"):
        op.add_column(table, sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"))
        op.create_check_constraint(f"ck_{table}_discount_nonnegative", table, "discount_amount >= 0")


def downgrade() -> None:
    for table in ("purchase_orders", "sales_orders"):
        op.drop_constraint(f"ck_{table}_shipping_nonnegative", table, type_="check")
        op.drop_column(table, "calculation_hash")
        op.drop_column(table, "shipping_charge")
    for table in ("purchase_order_items", "sales_quotation_items", "sales_order_items"):
        op.drop_index(f"ix_{table}_tenant_promotion", table_name=table)
        op.drop_index(f"ix_{table}_tenant_rule", table_name=table)
        op.drop_constraint(f"fk_{table}_promotion", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_pricing_rule", table, type_="foreignkey")
        op.drop_constraint(f"ck_{table}_discount_nonnegative", table, type_="check")
        op.drop_column(table, "is_free")
        op.drop_column(table, "promotion_id")
        op.drop_column(table, "pricing_rule_id")
        op.drop_column(table, "discount_amount")
    for table in ("supplier_invoice_items", "sales_invoice_items"):
        op.drop_constraint(f"ck_{table}_discount_nonnegative", table, type_="check")
        op.drop_column(table, "discount_amount")
    op.drop_constraint("ck_item_weight_nonnegative", "items", type_="check")
    op.drop_column("items", "weight_uom")
    op.drop_column("items", "weight_per_unit")
    op.drop_column("pricing_rules", "stackable")
    op.drop_constraint("ck_promo_free_item_required", "promotional_schemes", type_="check")
    op.drop_constraint("fk_promo_free_item", "promotional_schemes", type_="foreignkey")
    op.drop_column("promotional_schemes", "free_item_id")
    op.drop_constraint("fk_product_bundle_item_uom", "product_bundle_items", type_="foreignkey")
    op.drop_column("product_bundle_items", "uom_id")
    op.drop_constraint("ck_item_price_priority_nonnegative", "item_prices", type_="check")
    op.drop_constraint("uq_item_price_period", "item_prices", type_="unique")
    op.create_unique_constraint(
        "uq_item_price_period", "item_prices",
        ["tenant_id", "item_id", "price_list_id", "valid_from"],
    )
    op.drop_constraint("fk_item_price_uom", "item_prices", type_="foreignkey")
    op.drop_column("item_prices", "is_active")
    op.drop_column("item_prices", "priority")
    op.drop_column("item_prices", "uom_id")
