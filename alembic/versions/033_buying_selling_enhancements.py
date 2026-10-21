"""Add Phase B buying, selling, shipping, loyalty, and settings entities.

Revision ID: 033_buying_selling_enhancements
Revises: 032_shared_master_entities
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033_buying_selling_enhancements"
down_revision: str | None = "032_shared_master_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None
U = postgresql.UUID(as_uuid=True)

def common():
    return [sa.Column("tenant_id", U, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False)]
def table(name, pk, *columns, constraints=()):
    op.create_table(name, sa.Column(pk, U, primary_key=True, nullable=False), *common(), *columns, *constraints)
def tenant_index(name):
    op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])

def upgrade() -> None:
    table("supplier_groups", "supplier_group_id", sa.Column("group_name", sa.String(128), nullable=False), sa.Column("parent_id", U, sa.ForeignKey("supplier_groups.supplier_group_id")), sa.Column("lft", sa.Integer(), nullable=False), sa.Column("rgt", sa.Integer(), nullable=False), sa.Column("is_group", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "group_name", name="uq_supplier_group_tenant_name"),))
    table("purchase_taxes_and_charges_templates", "template_id", sa.Column("title", sa.String(128), nullable=False), sa.Column("tax_category", sa.String(64), nullable=False), sa.Column("is_default", sa.Boolean(), nullable=False), sa.Column("disabled", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "title", name="uq_purchase_tax_template_tenant_title"),))
    table("purchase_taxes_and_charges_template_details", "detail_id", sa.Column("template_id", U, sa.ForeignKey("purchase_taxes_and_charges_templates.template_id", ondelete="CASCADE"), nullable=False), sa.Column("charge_type", sa.String(32), nullable=False), sa.Column("row_id", sa.Integer()), sa.Column("account_head", sa.String(64), nullable=False), sa.Column("description", sa.String(255), nullable=False), sa.Column("rate", sa.Numeric(18,4), nullable=False), constraints=(sa.CheckConstraint("rate >= 0", name="ck_purchase_tax_rate_nonnegative"), sa.CheckConstraint("charge_type IN ('Actual','On Net Total','On Previous Row Amount')", name="ck_purchase_tax_charge_type")))
    table("shipping_rules", "shipping_rule_id", sa.Column("rule_name", sa.String(128), nullable=False), sa.Column("destination_country", sa.String(128)), sa.Column("destination_state", sa.String(128)), sa.Column("priority", sa.Integer(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "rule_name", name="uq_shipping_rule_tenant_name"),))
    table("shipping_rule_conditions", "condition_id", sa.Column("shipping_rule_id", U, sa.ForeignKey("shipping_rules.shipping_rule_id", ondelete="CASCADE"), nullable=False), sa.Column("based_on", sa.String(32), nullable=False), sa.Column("min_value", sa.Numeric(18,4)), sa.Column("max_value", sa.Numeric(18,4)), sa.Column("charge_type", sa.String(16), nullable=False), sa.Column("rate", sa.Numeric(18,4), nullable=False), constraints=(sa.CheckConstraint("based_on IN ('ORDER_VALUE','WEIGHT','ITEM_QTY')", name="ck_shipping_condition_based_on"), sa.CheckConstraint("charge_type IN ('FIXED','PER_UNIT','PERCENT')", name="ck_shipping_condition_charge_type"), sa.CheckConstraint("rate >= 0", name="ck_shipping_condition_rate_nonnegative"), sa.CheckConstraint("max_value IS NULL OR min_value IS NULL OR max_value >= min_value", name="ck_shipping_condition_range")))
    table("item_manufacturers", "item_manufacturer_id", sa.Column("item_id", U, sa.ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False), sa.Column("manufacturer_name", sa.String(255), nullable=False), sa.Column("manufacturer_part_no", sa.String(128)), sa.Column("is_default", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "item_id", "manufacturer_name", name="uq_item_manufacturer_tenant_item_name"),))
    table("promotional_schemes", "scheme_id", sa.Column("scheme_name", sa.String(128), nullable=False), sa.Column("scheme_type", sa.String(32), nullable=False), sa.Column("discount_type", sa.String(16), nullable=False), sa.Column("discount_value", sa.Numeric(18,4), nullable=False), sa.Column("buy_quantity", sa.Numeric(18,4)), sa.Column("free_quantity", sa.Numeric(18,4)), sa.Column("item_id", U, sa.ForeignKey("items.item_id", ondelete="CASCADE")), sa.Column("item_group_id", U, sa.ForeignKey("item_groups.item_group_id", ondelete="CASCADE")), sa.Column("valid_from", sa.Date()), sa.Column("valid_to", sa.Date()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "scheme_name", name="uq_promo_scheme_tenant_name"), sa.CheckConstraint("scheme_type IN ('DISCOUNT','BUY_X_GET_Y')", name="ck_promo_scheme_type"), sa.CheckConstraint("discount_type IN ('PERCENT','FIXED')", name="ck_promo_discount_type"), sa.CheckConstraint("discount_value >= 0 AND (discount_type <> 'PERCENT' OR discount_value <= 100)", name="ck_promo_discount_nonnegative"), sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_promo_dates"), sa.CheckConstraint("scheme_type <> 'BUY_X_GET_Y' OR (buy_quantity IS NOT NULL AND buy_quantity > 0 AND free_quantity IS NOT NULL AND free_quantity > 0)", name="ck_promo_buy_get_quantities")))
    table("pricing_rules", "pricing_rule_id", sa.Column("rule_name", sa.String(128), nullable=False), sa.Column("item_id", U, sa.ForeignKey("items.item_id", ondelete="CASCADE")), sa.Column("item_group_id", U, sa.ForeignKey("item_groups.item_group_id", ondelete="CASCADE")), sa.Column("price_list_id", U, sa.ForeignKey("price_lists.price_list_id", ondelete="CASCADE")), sa.Column("min_quantity", sa.Numeric(18,4), nullable=False), sa.Column("discount_type", sa.String(16), nullable=False), sa.Column("discount_value", sa.Numeric(18,4), nullable=False), sa.Column("priority", sa.Integer(), nullable=False), sa.Column("valid_from", sa.Date()), sa.Column("valid_to", sa.Date()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "rule_name", name="uq_pricing_rule_tenant_name"), sa.CheckConstraint("discount_type IN ('PERCENT','FIXED')", name="ck_pricing_rule_discount_type"), sa.CheckConstraint("min_quantity > 0 AND discount_value >= 0 AND (discount_type <> 'PERCENT' OR discount_value <= 100)", name="ck_pricing_rule_values"), sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_pricing_rule_dates")))
    table("sales_partners", "sales_partner_id", sa.Column("partner_name", sa.String(255), nullable=False), sa.Column("commission_rate", sa.Numeric(7,4), nullable=False), sa.Column("territory", sa.String(128)), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "partner_name", name="uq_sales_partner_tenant_name"), sa.CheckConstraint("commission_rate BETWEEN 0 AND 100", name="ck_sales_partner_commission_range")))
    table("sales_teams", "sales_team_id", sa.Column("document_type", sa.String(64), nullable=False), sa.Column("document_id", U, nullable=False), sa.Column("sales_partner_id", U, sa.ForeignKey("sales_partners.sales_partner_id", ondelete="CASCADE"), nullable=False), sa.Column("contribution_pct", sa.Numeric(7,4), nullable=False), sa.Column("commission_rate", sa.Numeric(7,4)), constraints=(sa.UniqueConstraint("tenant_id", "document_type", "document_id", "sales_partner_id", name="uq_sales_team_document_partner"), sa.CheckConstraint("contribution_pct BETWEEN 0 AND 100", name="ck_sales_team_contribution_range"), sa.CheckConstraint("commission_rate IS NULL OR commission_rate BETWEEN 0 AND 100", name="ck_sales_team_commission_range")))
    table("loyalty_programs", "loyalty_program_id", sa.Column("program_name", sa.String(128), nullable=False), sa.Column("points_per_currency", sa.Numeric(12,6), nullable=False), sa.Column("redemption_value_per_point", sa.Numeric(12,6), nullable=False), sa.Column("minimum_redemption_points", sa.Numeric(18,4), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "program_name", name="uq_loyalty_program_tenant_name"), sa.CheckConstraint("points_per_currency >= 0 AND redemption_value_per_point > 0 AND minimum_redemption_points >= 0", name="ck_loyalty_program_values")))
    table("loyalty_point_entries", "loyalty_entry_id", sa.Column("loyalty_program_id", U, sa.ForeignKey("loyalty_programs.loyalty_program_id"), nullable=False), sa.Column("customer_id", U, sa.ForeignKey("customers.customer_id"), nullable=False), sa.Column("invoice_id", U), sa.Column("entry_type", sa.String(16), nullable=False), sa.Column("points", sa.Numeric(18,4), nullable=False), sa.Column("posting_date", sa.Date(), nullable=False), sa.Column("remarks", sa.Text()), constraints=(sa.CheckConstraint("entry_type IN ('EARN','REDEEM')", name="ck_loyalty_entry_type"), sa.CheckConstraint("points > 0", name="ck_loyalty_entry_points_positive"), sa.UniqueConstraint("tenant_id", "loyalty_program_id", "customer_id", "invoice_id", "entry_type", name="uq_loyalty_invoice_entry")))
    op.add_column("suppliers", sa.Column("supplier_group_id", U, sa.ForeignKey("supplier_groups.supplier_group_id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_suppliers_supplier_group_id", "suppliers", ["supplier_group_id"])
    op.add_column("tenant_settings", sa.Column("auto_material_request", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tenant_settings", sa.Column("allow_negative_stock", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tenant_settings", sa.Column("over_receipt_percentage", sa.Numeric(5,2), nullable=False, server_default="0"))
    op.add_column("tenant_settings", sa.Column("over_billing_percentage", sa.Numeric(5,2), nullable=False, server_default="0"))
    op.add_column("tenant_settings", sa.Column("backflush_based_on", sa.String(32), nullable=False, server_default="BOM"))
    for name in ("supplier_groups", "purchase_taxes_and_charges_templates", "purchase_taxes_and_charges_template_details", "shipping_rules", "shipping_rule_conditions", "item_manufacturers", "promotional_schemes", "pricing_rules", "sales_partners", "sales_teams", "loyalty_programs", "loyalty_point_entries"):
        tenant_index(name)
    for idx, table_name, cols in [
        ("ix_supplier_group_tenant_parent", "supplier_groups", ["tenant_id", "parent_id"]),
        ("ix_purchase_tax_detail_tenant_template", "purchase_taxes_and_charges_template_details", ["tenant_id", "template_id"]),
        ("ix_shipping_rule_tenant_priority", "shipping_rules", ["tenant_id", "priority"]),
        ("ix_shipping_condition_tenant_rule", "shipping_rule_conditions", ["tenant_id", "shipping_rule_id"]),
        ("ix_item_manufacturer_tenant_item", "item_manufacturers", ["tenant_id", "item_id"]),
        ("ix_pricing_rule_tenant_priority", "pricing_rules", ["tenant_id", "priority"]),
        ("ix_sales_team_tenant_document", "sales_teams", ["tenant_id", "document_type", "document_id"]),
        ("ix_loyalty_entry_tenant_customer_date", "loyalty_point_entries", ["tenant_id", "customer_id", "posting_date"]),
    ]:
        op.create_index(idx, table_name, cols)

def downgrade() -> None:
    for column in ("backflush_based_on", "over_billing_percentage", "over_receipt_percentage", "allow_negative_stock", "auto_material_request"):
        op.drop_column("tenant_settings", column)
    op.drop_index("ix_suppliers_supplier_group_id", table_name="suppliers")
    op.drop_column("suppliers", "supplier_group_id")
    for name in ("loyalty_point_entries", "loyalty_programs", "sales_teams", "sales_partners", "pricing_rules", "promotional_schemes", "item_manufacturers", "shipping_rule_conditions", "shipping_rules", "purchase_taxes_and_charges_template_details", "purchase_taxes_and_charges_templates", "supplier_groups"):
        op.drop_table(name)
