"""Add document tax-template snapshots and full chained tax semantics.

Revision ID: 041_commercial_tax_snapshots
Revises: 040_commercial_calculation_context
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "041_commercial_tax_snapshots"
down_revision: str | None = "040_commercial_calculation_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    for column, type_ in (
        ("uom_id", UUID), ("price_list_id", UUID), ("item_price_id", UUID),
        ("price_list_rate", sa.Numeric(18, 4)),
    ):
        op.add_column("sales_quotation_items", sa.Column(column, type_, nullable=True))
    op.add_column("sales_quotation_items", sa.Column("conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("sales_quotation_items", sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"))
    for name, column, target_table, target in (
        ("fk_sales_quotation_item_uom", "uom_id", "uoms", "uom_id"),
        ("fk_sales_quotation_item_price_list", "price_list_id", "price_lists", "price_list_id"),
        ("fk_sales_quotation_item_price", "item_price_id", "item_prices", "item_price_id"),
    ):
        op.create_foreign_key(name, "sales_quotation_items", target_table, [column], [target])
    op.create_check_constraint("ck_sales_quotation_item_uom_positive", "sales_quotation_items", "conversion_factor > 0 AND stock_quantity >= 0")
    for table, field, target_table in (
        ("purchase_orders", "purchase_tax_template_id", "purchase_taxes_and_charges_templates"),
        ("sales_orders", "sales_tax_template_id", "sales_taxes_and_charges_templates"),
        ("sales_quotations", "sales_tax_template_id", "sales_taxes_and_charges_templates"),
    ):
        op.add_column(table, sa.Column(field, UUID, nullable=True))
        op.create_foreign_key(f"fk_{table}_{field}", table, target_table, [field], ["template_id"])
        op.create_index(f"ix_{table}_tenant_{field}", table, ["tenant_id", field])
    for table in ("purchase_orders", "sales_orders", "sales_quotations"):
        op.add_column(table, sa.Column("tax_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("sales_quotations", sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"))
    op.add_column("sales_quotations", sa.Column("price_list_id", UUID, nullable=True))
    op.add_column("sales_quotations", sa.Column("shipping_rule_id", UUID, nullable=True))
    op.add_column("sales_quotations", sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("sales_quotations", sa.Column("shipping_charge", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("sales_quotations", sa.Column("calculation_hash", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_sales_quotation_price_list", "sales_quotations", "price_lists", ["price_list_id"], ["price_list_id"])
    op.create_foreign_key("fk_sales_quotation_shipping_rule", "sales_quotations", "shipping_rules", ["shipping_rule_id"], ["shipping_rule_id"])
    op.create_check_constraint("ck_sales_quotation_discount_nonnegative", "sales_quotations", "discount_amount >= 0")
    op.create_check_constraint("ck_sales_quotation_shipping_nonnegative", "sales_quotations", "shipping_charge >= 0")
    op.drop_constraint("ck_purchase_tax_charge_type", "purchase_taxes_and_charges_template_details", type_="check")
    op.create_check_constraint(
        "ck_purchase_tax_charge_type", "purchase_taxes_and_charges_template_details",
        "charge_type IN ('Actual','On Net Total','On Previous Row Amount','On Previous Row Total','On Item Quantity')",
    )
    for table in ("purchase_taxes_and_charges_template_details", "sales_taxes_and_charges_template_details"):
        op.add_column(table, sa.Column("reference_row", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("included_in_rate", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("add_deduct", sa.String(length=8), nullable=False, server_default="ADD"))
        op.add_column(table, sa.Column("consider_for_valuation", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_check_constraint(f"ck_{table}_add_deduct", table, "add_deduct IN ('ADD','DEDUCT')")
    op.create_check_constraint(
        "ck_sales_tax_charge_type", "sales_taxes_and_charges_template_details",
        "charge_type IN ('Actual','On Net Total','On Previous Row Amount','On Previous Row Total','On Item Quantity')",
    )
    op.create_check_constraint("ck_sales_tax_rate_nonnegative", "sales_taxes_and_charges_template_details", "rate >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_sales_quotation_item_uom_positive", "sales_quotation_items", type_="check")
    for name, column in (
        ("fk_sales_quotation_item_price", "item_price_id"),
        ("fk_sales_quotation_item_price_list", "price_list_id"),
        ("fk_sales_quotation_item_uom", "uom_id"),
    ):
        op.drop_constraint(name, "sales_quotation_items", type_="foreignkey")
    for column in ("stock_quantity", "conversion_factor", "price_list_rate", "item_price_id", "price_list_id", "uom_id"):
        op.drop_column("sales_quotation_items", column)
    op.drop_constraint("ck_sales_tax_rate_nonnegative", "sales_taxes_and_charges_template_details", type_="check")
    op.drop_constraint("ck_sales_tax_charge_type", "sales_taxes_and_charges_template_details", type_="check")
    for table in ("purchase_taxes_and_charges_template_details", "sales_taxes_and_charges_template_details"):
        op.drop_constraint(f"ck_{table}_add_deduct", table, type_="check")
        for column in ("consider_for_valuation", "add_deduct", "included_in_rate", "reference_row"):
            op.drop_column(table, column)
    op.drop_constraint("ck_purchase_tax_charge_type", "purchase_taxes_and_charges_template_details", type_="check")
    op.create_check_constraint(
        "ck_purchase_tax_charge_type", "purchase_taxes_and_charges_template_details",
        "charge_type IN ('Actual','On Net Total','On Previous Row Amount')",
    )
    op.drop_constraint("ck_sales_quotation_shipping_nonnegative", "sales_quotations", type_="check")
    op.drop_constraint("ck_sales_quotation_discount_nonnegative", "sales_quotations", type_="check")
    op.drop_constraint("fk_sales_quotation_shipping_rule", "sales_quotations", type_="foreignkey")
    op.drop_constraint("fk_sales_quotation_price_list", "sales_quotations", type_="foreignkey")
    for column in ("calculation_hash", "shipping_charge", "discount_amount", "shipping_rule_id", "price_list_id", "currency"):
        op.drop_column("sales_quotations", column)
    for table, field in (
        ("purchase_orders", "purchase_tax_template_id"),
        ("sales_orders", "sales_tax_template_id"),
        ("sales_quotations", "sales_tax_template_id"),
    ):
        op.drop_index(f"ix_{table}_tenant_{field}", table_name=table)
        op.drop_constraint(f"fk_{table}_{field}", table, type_="foreignkey")
        op.drop_column(table, field)
    for table in ("purchase_orders", "sales_orders", "sales_quotations"):
        op.drop_column(table, "tax_snapshot")
