"""Create shared Phase A master data entities.

Revision ID: 032_shared_master_entities
Revises: 031_stock_ledger_serial_number
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032_shared_master_entities"
down_revision: str | None = "031_stock_ledger_serial_number"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

U = postgresql.UUID(as_uuid=True)

def common():
    return [sa.Column("tenant_id", U, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False)]

def table(name, pk, *columns, constraints=()):
    op.create_table(name, sa.Column(pk, U, primary_key=True, nullable=False), *common(), *columns, *constraints)

def upgrade() -> None:
    table("item_groups", "item_group_id", sa.Column("group_name", sa.String(128), nullable=False), sa.Column("parent_id", U, sa.ForeignKey("item_groups.item_group_id")), sa.Column("lft", sa.Integer(), nullable=False), sa.Column("rgt", sa.Integer(), nullable=False), sa.Column("is_group", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "group_name", name="uq_item_group_tenant_name"),))
    table("price_lists", "price_list_id", sa.Column("price_list_name", sa.String(128), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("selling", sa.Boolean(), nullable=False), sa.Column("buying", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "price_list_name", name="uq_price_list_tenant_name"), sa.CheckConstraint("selling OR buying", name="ck_price_list_has_context")))
    table("item_prices", "item_price_id", sa.Column("item_id", U, sa.ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False), sa.Column("price_list_id", U, sa.ForeignKey("price_lists.price_list_id", ondelete="CASCADE"), nullable=False), sa.Column("rate", sa.Numeric(18,4), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("valid_from", sa.Date()), sa.Column("valid_to", sa.Date()), constraints=(sa.UniqueConstraint("tenant_id", "item_id", "price_list_id", "valid_from", name="uq_item_price_period"), sa.CheckConstraint("rate >= 0", name="ck_item_price_nonnegative")))
    table("contacts", "contact_id", sa.Column("full_name", sa.String(255), nullable=False), sa.Column("email", sa.String(255)), sa.Column("phone", sa.String(64)), sa.Column("designation", sa.String(128)), sa.Column("link_doctype", sa.String(64)), sa.Column("link_name", sa.String(128)), sa.Column("is_primary", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False))
    table("addresses", "address_id", sa.Column("address_title", sa.String(255), nullable=False), sa.Column("address_type", sa.String(32), nullable=False), sa.Column("address_line1", sa.String(255), nullable=False), sa.Column("address_line2", sa.String(255)), sa.Column("city", sa.String(128), nullable=False), sa.Column("state", sa.String(128)), sa.Column("postal_code", sa.String(32)), sa.Column("country", sa.String(128), nullable=False), sa.Column("link_doctype", sa.String(64)), sa.Column("link_name", sa.String(128)), sa.Column("is_primary", sa.Boolean(), nullable=False), constraints=(sa.CheckConstraint("address_type IN ('BILLING','SHIPPING','OFFICE','OTHER')", name="ck_address_type"),))
    table("uoms", "uom_id", sa.Column("uom_name", sa.String(64), nullable=False), sa.Column("abbreviation", sa.String(16), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "uom_name", name="uq_uom_tenant_name"), sa.UniqueConstraint("tenant_id", "abbreviation", name="uq_uom_tenant_abbreviation")))
    table("uom_conversions", "conversion_id", sa.Column("from_uom_id", U, sa.ForeignKey("uoms.uom_id", ondelete="CASCADE"), nullable=False), sa.Column("to_uom_id", U, sa.ForeignKey("uoms.uom_id", ondelete="CASCADE"), nullable=False), sa.Column("factor", sa.Numeric(18,8), nullable=False), sa.Column("item_id", U, sa.ForeignKey("items.item_id", ondelete="CASCADE")), constraints=(sa.UniqueConstraint("tenant_id", "from_uom_id", "to_uom_id", "item_id", name="uq_uom_conversion"), sa.CheckConstraint("factor > 0", name="ck_uom_conversion_positive"), sa.CheckConstraint("from_uom_id <> to_uom_id", name="ck_uom_conversion_distinct")))
    table("naming_series", "naming_series_id", sa.Column("document_type", sa.String(64), nullable=False), sa.Column("prefix", sa.String(32), nullable=False), sa.Column("current_number", sa.Integer(), nullable=False), sa.Column("number_width", sa.Integer(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "document_type", "prefix", name="uq_naming_series_tenant_doc_prefix"), sa.CheckConstraint("current_number >= 0", name="ck_naming_series_nonnegative"), sa.CheckConstraint("number_width BETWEEN 1 AND 12", name="ck_naming_series_width")))
    table("terms_and_conditions_templates", "terms_template_id", sa.Column("template_name", sa.String(128), nullable=False), sa.Column("terms", sa.Text(), nullable=False), sa.Column("applicable_to", sa.String(32), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "template_name", name="uq_terms_template_tenant_name"), sa.CheckConstraint("applicable_to IN ('BUYING','SELLING','BOTH')", name="ck_terms_template_applicable")))
    table("product_bundles", "bundle_id", sa.Column("bundle_item_id", U, sa.ForeignKey("items.item_id"), nullable=False), sa.Column("bundle_name", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "bundle_item_id", name="uq_product_bundle_item"),))
    table("product_bundle_items", "bundle_line_id", sa.Column("bundle_id", U, sa.ForeignKey("product_bundles.bundle_id", ondelete="CASCADE"), nullable=False), sa.Column("item_id", U, sa.ForeignKey("items.item_id"), nullable=False), sa.Column("quantity", sa.Numeric(18,4), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "bundle_id", "item_id", name="uq_product_bundle_component"), sa.CheckConstraint("quantity > 0", name="ck_product_bundle_item_quantity")))
    table("issue_types", "issue_type_id", sa.Column("type_name", sa.String(128), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "type_name", name="uq_issue_type_tenant_name"),))
    op.add_column("items", sa.Column("item_group_id", U, sa.ForeignKey("item_groups.item_group_id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_items_item_group_id", "items", ["item_group_id"])
    for name in ("item_groups", "price_lists", "item_prices", "contacts", "addresses", "uoms", "uom_conversions", "naming_series", "terms_and_conditions_templates", "product_bundles", "product_bundle_items", "issue_types"):
        op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
    op.create_index("ix_item_group_tenant_parent", "item_groups", ["tenant_id", "parent_id"])
    op.create_index("ix_contact_tenant_dynamic_link", "contacts", ["tenant_id", "link_doctype", "link_name"])
    op.create_index("ix_contact_tenant_email", "contacts", ["tenant_id", "email"])
    op.create_index("ix_address_tenant_dynamic_link", "addresses", ["tenant_id", "link_doctype", "link_name"])
    op.create_index("ix_item_price_tenant_list_item", "item_prices", ["tenant_id", "price_list_id", "item_id"])

def downgrade() -> None:
    op.drop_index("ix_items_item_group_id", table_name="items")
    op.drop_column("items", "item_group_id")
    for name in ("product_bundle_items", "product_bundles", "terms_and_conditions_templates", "naming_series", "uom_conversions", "uoms", "addresses", "contacts", "item_prices", "price_lists", "item_groups", "issue_types"):
        op.drop_table(name)
