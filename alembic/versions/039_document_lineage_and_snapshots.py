"""Add immutable commercial snapshots and source-line lineage.

Revision ID: 039_document_lineage_and_snapshots
Revises: 038_payroll_currency_and_period_guard
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "039_document_lineage_and_snapshots"
down_revision: str | None = "038_payroll_currency_and_period_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

UUID = postgresql.UUID(as_uuid=True)
MONEY = sa.Numeric(18, 4)
RATE = sa.Numeric(18, 8)


def _add_fk(name: str, source_table: str, source_column: str, target_table: str, target_column: str) -> None:
    op.create_foreign_key(name, source_table, target_table, [source_column], [target_column])


def upgrade() -> None:
    for column in ("amended_from_po_id",):
        op.add_column("purchase_orders", sa.Column(column, UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    _add_fk("fk_purchase_order_amended_from", "purchase_orders", "amended_from_po_id", "purchase_orders", "po_id")
    op.create_index("ix_purchase_order_tenant_amended_from", "purchase_orders", ["tenant_id", "amended_from_po_id"])
    op.execute("UPDATE purchase_orders SET submitted_at = created_at WHERE status IN ('SUBMITTED','PARTIALLY_RECEIVED','COMPLETED')")
    op.add_column("sales_orders", sa.Column("amended_from_order_id", UUID, nullable=True))
    op.add_column("sales_orders", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    _add_fk("fk_sales_order_amended_from", "sales_orders", "amended_from_order_id", "sales_orders", "order_id")
    op.create_index("ix_sales_order_tenant_amended_from", "sales_orders", ["tenant_id", "amended_from_order_id"])
    op.execute("UPDATE sales_orders SET submitted_at = created_at WHERE status IN ('CONFIRMED','BACKORDERED','PARTIALLY_DELIVERED','DELIVERED')")
    # Purchase-document header snapshots.
    op.add_column("purchase_orders", sa.Column("material_request_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("supplier_contact_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("supplier_contact_snapshot", postgresql.JSONB, nullable=True))
    op.add_column("purchase_orders", sa.Column("supplier_address_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("supplier_address_snapshot", postgresql.JSONB, nullable=True))
    op.add_column("purchase_orders", sa.Column("shipping_address_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("shipping_address_snapshot", postgresql.JSONB, nullable=True))
    op.add_column("purchase_orders", sa.Column("terms_template_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("terms_text", sa.Text(), nullable=True))
    op.add_column("purchase_orders", sa.Column("payment_terms", sa.String(length=255), nullable=True))
    op.add_column("purchase_orders", sa.Column("incoterm", sa.String(length=32), nullable=True))
    op.add_column("purchase_orders", sa.Column("shipping_rule_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("exchange_rate", RATE, nullable=False, server_default="1.00000000"))
    op.add_column("purchase_orders", sa.Column("target_warehouse_id", UUID, nullable=True))
    op.add_column("purchase_orders", sa.Column("discount_amount", MONEY, nullable=False, server_default="0"))
    op.add_column("purchase_orders", sa.Column("taxes_and_charges", MONEY, nullable=False, server_default="0"))
    for name, column, table, target in (
        ("fk_purchase_order_material_request", "material_request_id", "material_requests", "mr_id"),
        ("fk_purchase_order_supplier_contact", "supplier_contact_id", "contacts", "contact_id"),
        ("fk_purchase_order_supplier_address", "supplier_address_id", "addresses", "address_id"),
        ("fk_purchase_order_shipping_address", "shipping_address_id", "addresses", "address_id"),
        ("fk_purchase_order_terms_template", "terms_template_id", "terms_and_conditions_templates", "terms_template_id"),
        ("fk_purchase_order_shipping_rule", "shipping_rule_id", "shipping_rules", "shipping_rule_id"),
        ("fk_purchase_order_target_warehouse", "target_warehouse_id", "warehouses", "warehouse_id"),
    ):
        _add_fk(name, "purchase_orders", column, table, target)
    op.create_index("ix_purchase_order_tenant_material_request", "purchase_orders", ["tenant_id", "material_request_id"])
    op.create_check_constraint("ck_purchase_order_exchange_rate_positive", "purchase_orders", "exchange_rate > 0")
    op.create_check_constraint("ck_purchase_order_discount_nonnegative", "purchase_orders", "discount_amount >= 0")

    # Purchase-document source-line links and commercial snapshot fields.
    for column, type_ in (
        ("material_request_item_id", UUID), ("rfq_item_id", UUID), ("supplier_quotation_item_id", UUID),
        ("uom_id", UUID), ("target_warehouse_id", UUID), ("price_list_id", UUID), ("item_price_id", UUID),
        ("price_list_rate", MONEY),
    ):
        op.add_column("purchase_order_items", sa.Column(column, type_, nullable=True))
    op.add_column("purchase_order_items", sa.Column("conversion_factor", RATE, nullable=False, server_default="1.00000000"))
    op.add_column("purchase_order_items", sa.Column("stock_quantity", MONEY, nullable=False, server_default="0"))
    for name, column, table, target in (
        ("fk_purchase_order_item_mr_item", "material_request_item_id", "material_request_items", "mr_item_id"),
        ("fk_purchase_order_item_rfq_item", "rfq_item_id", "rfq_items", "rfq_item_id"),
        ("fk_purchase_order_item_sq_item", "supplier_quotation_item_id", "supplier_quotation_items", "sq_item_id"),
        ("fk_purchase_order_item_uom", "uom_id", "uoms", "uom_id"),
        ("fk_purchase_order_item_warehouse", "target_warehouse_id", "warehouses", "warehouse_id"),
        ("fk_purchase_order_item_price_list", "price_list_id", "price_lists", "price_list_id"),
        ("fk_purchase_order_item_price", "item_price_id", "item_prices", "item_price_id"),
    ):
        _add_fk(name, "purchase_order_items", column, table, target)
    op.create_index("ix_purchase_order_item_tenant_mr_item", "purchase_order_items", ["tenant_id", "material_request_item_id"])
    op.create_index("ix_purchase_order_item_tenant_sq_item", "purchase_order_items", ["tenant_id", "supplier_quotation_item_id"])
    op.create_check_constraint("ck_purchase_order_item_conversion_positive", "purchase_order_items", "conversion_factor > 0")
    op.create_check_constraint("ck_purchase_order_item_stock_quantity_nonnegative", "purchase_order_items", "stock_quantity >= 0")
    op.execute("UPDATE purchase_order_items SET stock_quantity = quantity WHERE stock_quantity = 0")

    # Downstream purchase-document lineage.
    op.add_column("goods_receipt_note_items", sa.Column("material_request_item_id", UUID, nullable=True))
    op.add_column("goods_receipt_note_items", sa.Column("supplier_quotation_item_id", UUID, nullable=True))
    _add_fk("fk_grn_item_mr_item", "goods_receipt_note_items", "material_request_item_id", "material_request_items", "mr_item_id")
    _add_fk("fk_grn_item_sq_item", "goods_receipt_note_items", "supplier_quotation_item_id", "supplier_quotation_items", "sq_item_id")
    op.add_column("supplier_invoice_items", sa.Column("po_item_id", UUID, nullable=True))
    op.add_column("supplier_invoice_items", sa.Column("grn_item_id", UUID, nullable=True))
    _add_fk("fk_supplier_invoice_item_po_item", "supplier_invoice_items", "po_item_id", "purchase_order_items", "item_line_id")
    _add_fk("fk_supplier_invoice_item_grn_item", "supplier_invoice_items", "grn_item_id", "goods_receipt_note_items", "grn_item_id")
    op.create_index("ix_supplier_invoice_item_tenant_po_item", "supplier_invoice_items", ["tenant_id", "po_item_id"])
    op.create_index("ix_supplier_invoice_item_tenant_grn_item", "supplier_invoice_items", ["tenant_id", "grn_item_id"])

    # Sales-document header snapshots.
    for column, type_ in (
        ("source_quotation_id", UUID), ("customer_contact_id", UUID), ("billing_address_id", UUID),
        ("shipping_address_id", UUID), ("terms_template_id", UUID), ("price_list_id", UUID), ("shipping_rule_id", UUID),
        ("terms_text", sa.Text()), ("payment_terms", sa.String(length=255)),
        ("customer_contact_snapshot", postgresql.JSONB), ("billing_address_snapshot", postgresql.JSONB),
        ("shipping_address_snapshot", postgresql.JSONB),
    ):
        op.add_column("sales_orders", sa.Column(column, type_, nullable=True))
    for column, type_, default in (
        ("exchange_rate", RATE, "1.00000000"), ("subtotal", MONEY, "0"), ("tax_amount", MONEY, "0"),
        ("discount_amount", MONEY, "0"), ("taxes_and_charges", MONEY, "0"),
    ):
        op.add_column("sales_orders", sa.Column(column, type_, nullable=False, server_default=default))
    for name, column, table, target in (
        ("fk_sales_order_source_quote", "source_quotation_id", "sales_quotations", "quotation_id"),
        ("fk_sales_order_customer_contact", "customer_contact_id", "contacts", "contact_id"),
        ("fk_sales_order_billing_address", "billing_address_id", "addresses", "address_id"),
        ("fk_sales_order_shipping_address", "shipping_address_id", "addresses", "address_id"),
        ("fk_sales_order_terms_template", "terms_template_id", "terms_and_conditions_templates", "terms_template_id"),
        ("fk_sales_order_price_list", "price_list_id", "price_lists", "price_list_id"),
        ("fk_sales_order_shipping_rule", "shipping_rule_id", "shipping_rules", "shipping_rule_id"),
    ):
        _add_fk(name, "sales_orders", column, table, target)
    op.create_index("ix_sales_order_tenant_source_quotation", "sales_orders", ["tenant_id", "source_quotation_id"])
    op.create_check_constraint("ck_sales_order_exchange_rate_positive", "sales_orders", "exchange_rate > 0")
    op.create_check_constraint("ck_sales_order_discount_nonnegative", "sales_orders", "discount_amount >= 0")

    op.create_table(
        "sales_quotation_items",
        sa.Column("quotation_item_id", UUID, primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("quotation_id", UUID, sa.ForeignKey("sales_quotations.quotation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", UUID, sa.ForeignKey("items.item_id"), nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("unit_price", MONEY, nullable=False),
        sa.Column("line_total", MONEY, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("quantity > 0", name="ck_sales_quotation_item_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_sales_quotation_item_amounts_nonnegative"),
    )
    op.create_index("ix_sales_quotation_item_tenant_quote", "sales_quotation_items", ["tenant_id", "quotation_id"])
    op.add_column("sales_order_items", sa.Column("source_quotation_item_id", UUID, nullable=True))
    _add_fk("fk_sales_order_item_source_quote_item", "sales_order_items", "source_quotation_item_id", "sales_quotation_items", "quotation_item_id")
    op.create_index("ix_sales_order_item_tenant_source_quote", "sales_order_items", ["tenant_id", "source_quotation_item_id"])

    for column, type_ in (("uom_id", UUID), ("price_list_id", UUID), ("item_price_id", UUID), ("price_list_rate", MONEY)):
        op.add_column("sales_order_items", sa.Column(column, type_, nullable=True))
    for column, type_, default in (
        ("conversion_factor", RATE, "1.00000000"), ("stock_quantity", MONEY, "0"),
        ("delivered_quantity", MONEY, "0"), ("invoiced_quantity", MONEY, "0"), ("returned_quantity", MONEY, "0"),
    ):
        op.add_column("sales_order_items", sa.Column(column, type_, nullable=False, server_default=default))
    for name, column, table, target in (
        ("fk_sales_order_item_uom", "uom_id", "uoms", "uom_id"),
        ("fk_sales_order_item_price_list", "price_list_id", "price_lists", "price_list_id"),
        ("fk_sales_order_item_price", "item_price_id", "item_prices", "item_price_id"),
    ):
        _add_fk(name, "sales_order_items", column, table, target)
    for name, condition in (
        ("ck_sales_order_item_conversion_positive", "conversion_factor > 0"),
        ("ck_sales_order_item_stock_quantity_nonnegative", "stock_quantity >= 0"),
        ("ck_sales_order_item_delivered_nonnegative", "delivered_quantity >= 0"),
        ("ck_sales_order_item_invoiced_nonnegative", "invoiced_quantity >= 0"),
        ("ck_sales_order_item_returned_nonnegative", "returned_quantity >= 0"),
    ):
        op.create_check_constraint(name, "sales_order_items", condition)

    op.add_column("sales_invoice_items", sa.Column("order_item_id", UUID, nullable=True))
    op.add_column("sales_invoice_items", sa.Column("delivery_note_item_id", UUID, nullable=True))
    _add_fk("fk_sales_invoice_item_order_item", "sales_invoice_items", "order_item_id", "sales_order_items", "order_item_id")
    _add_fk("fk_sales_invoice_item_dn_item", "sales_invoice_items", "delivery_note_item_id", "delivery_note_items", "dn_item_id")
    op.create_index("ix_sales_invoice_item_tenant_order_item", "sales_invoice_items", ["tenant_id", "order_item_id"])
    op.create_index("ix_sales_invoice_item_tenant_dn_item", "sales_invoice_items", ["tenant_id", "delivery_note_item_id"])

    # Backfill operational counters for pre-existing documents. Existing order
    # quantities were stored in stock UOM and invoices were generated per delivery.
    op.execute("UPDATE sales_order_items SET stock_quantity = quantity WHERE stock_quantity = 0")
    op.execute("UPDATE sales_orders SET subtotal = total_amount WHERE subtotal = 0")
    op.execute(
        """UPDATE sales_order_items soi
           SET delivered_quantity = COALESCE((
               SELECT SUM(dni.quantity) FROM delivery_note_items dni
               JOIN delivery_notes dn ON dn.delivery_note_id = dni.delivery_note_id
               WHERE dni.tenant_id = soi.tenant_id AND dni.order_item_id = soi.order_item_id
                 AND dn.status <> 'CANCELLED'
           ), 0)"""
    )
    op.execute(
        """UPDATE sales_order_items soi
           SET invoiced_quantity = COALESCE((
               SELECT SUM(sii.quantity) FROM sales_invoice_items sii
               JOIN sales_invoices si ON si.invoice_id = sii.invoice_id
               WHERE sii.tenant_id = soi.tenant_id AND sii.delivery_note_item_id IN (
                   SELECT dni.dn_item_id FROM delivery_note_items dni
                   WHERE dni.tenant_id = soi.tenant_id AND dni.order_item_id = soi.order_item_id
               ) AND si.status <> 'CANCELLED'
           ), 0)"""
    )

    # Material-request details and immutable terms snapshot.
    op.add_column("material_requests", sa.Column("requester_employee_id", UUID, nullable=True))
    op.add_column("material_requests", sa.Column("external_reference", sa.String(length=255), nullable=True))
    op.add_column("material_requests", sa.Column("terms_template_id", UUID, nullable=True))
    op.add_column("material_requests", sa.Column("terms_text", sa.Text(), nullable=True))
    _add_fk("fk_material_request_requester", "material_requests", "requester_employee_id", "employees", "employee_id")
    _add_fk("fk_material_request_terms_template", "material_requests", "terms_template_id", "terms_and_conditions_templates", "terms_template_id")

    op.create_table(
        "document_audit_batches",
        sa.Column("batch_id", UUID, primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "operation", "idempotency_key", name="uq_document_audit_batch_idempotency"),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name="ck_document_audit_batch_status"),
    )
    op.create_index("ix_document_audit_batch_tenant_operation", "document_audit_batches", ["tenant_id", "operation", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_sales_order_tenant_amended_from", table_name="sales_orders")
    op.drop_constraint("fk_sales_order_amended_from", "sales_orders", type_="foreignkey")
    for column in ("cancelled_at", "submitted_at", "amended_from_order_id"):
        op.drop_column("sales_orders", column)
    op.drop_index("ix_purchase_order_tenant_amended_from", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_order_amended_from", "purchase_orders", type_="foreignkey")
    for column in ("cancelled_at", "submitted_at", "amended_from_po_id"):
        op.drop_column("purchase_orders", column)
    op.drop_index("ix_document_audit_batch_tenant_operation", table_name="document_audit_batches")
    op.drop_table("document_audit_batches")
    for name, table in (
        ("fk_material_request_terms_template", "material_requests"),
        ("fk_material_request_requester", "material_requests"),
    ):
        op.drop_constraint(name, table, type_="foreignkey")
    for column in ("terms_text", "terms_template_id", "external_reference", "requester_employee_id"):
        op.drop_column("material_requests", column)
    for name, table in (
        ("ix_sales_invoice_item_tenant_dn_item", "sales_invoice_items"),
        ("ix_sales_invoice_item_tenant_order_item", "sales_invoice_items"),
    ):
        op.drop_index(name, table_name=table)
    op.drop_constraint("fk_sales_invoice_item_dn_item", "sales_invoice_items", type_="foreignkey")
    op.drop_constraint("fk_sales_invoice_item_order_item", "sales_invoice_items", type_="foreignkey")
    op.drop_column("sales_invoice_items", "delivery_note_item_id")
    op.drop_column("sales_invoice_items", "order_item_id")
    op.drop_index("ix_sales_order_item_tenant_source_quote", table_name="sales_order_items")
    op.drop_constraint("fk_sales_order_item_source_quote_item", "sales_order_items", type_="foreignkey")
    op.drop_column("sales_order_items", "source_quotation_item_id")
    op.drop_index("ix_sales_quotation_item_tenant_quote", table_name="sales_quotation_items")
    op.drop_table("sales_quotation_items")
    for name in (
        "ck_sales_order_item_returned_nonnegative", "ck_sales_order_item_invoiced_nonnegative",
        "ck_sales_order_item_delivered_nonnegative", "ck_sales_order_item_stock_quantity_nonnegative",
        "ck_sales_order_item_conversion_positive",
    ):
        op.drop_constraint(name, "sales_order_items", type_="check")
    for name in ("fk_sales_order_item_price", "fk_sales_order_item_price_list", "fk_sales_order_item_uom"):
        op.drop_constraint(name, "sales_order_items", type_="foreignkey")
    for column in ("returned_quantity", "invoiced_quantity", "delivered_quantity", "stock_quantity", "conversion_factor", "price_list_rate", "item_price_id", "price_list_id", "uom_id"):
        op.drop_column("sales_order_items", column)
    for name in ("ck_sales_order_taxes_nonnegative", "ck_sales_order_discount_nonnegative", "ck_sales_order_exchange_rate_positive"):
        op.drop_constraint(name, "sales_orders", type_="check")
    op.drop_index("ix_sales_order_tenant_source_quotation", table_name="sales_orders")
    for name in ("fk_sales_order_shipping_rule", "fk_sales_order_price_list", "fk_sales_order_terms_template", "fk_sales_order_shipping_address", "fk_sales_order_billing_address", "fk_sales_order_customer_contact", "fk_sales_order_source_quote"):
        op.drop_constraint(name, "sales_orders", type_="foreignkey")
    for column in ("taxes_and_charges", "discount_amount", "tax_amount", "subtotal", "exchange_rate", "payment_terms", "terms_text", "shipping_rule_id", "price_list_id", "terms_template_id", "shipping_address_snapshot", "shipping_address_id", "billing_address_snapshot", "billing_address_id", "customer_contact_snapshot", "customer_contact_id", "source_quotation_id"):
        op.drop_column("sales_orders", column)
    for name, table in (("ix_supplier_invoice_item_tenant_grn_item", "supplier_invoice_items"), ("ix_supplier_invoice_item_tenant_po_item", "supplier_invoice_items")):
        op.drop_index(name, table_name=table)
    for name, table in (("fk_supplier_invoice_item_grn_item", "supplier_invoice_items"), ("fk_supplier_invoice_item_po_item", "supplier_invoice_items"), ("fk_grn_item_sq_item", "goods_receipt_note_items"), ("fk_grn_item_mr_item", "goods_receipt_note_items")):
        op.drop_constraint(name, table, type_="foreignkey")
    for table, column in (("supplier_invoice_items", "grn_item_id"), ("supplier_invoice_items", "po_item_id"), ("goods_receipt_note_items", "supplier_quotation_item_id"), ("goods_receipt_note_items", "material_request_item_id")):
        op.drop_column(table, column)
    for name in ("ck_purchase_order_item_stock_quantity_nonnegative", "ck_purchase_order_item_conversion_positive"):
        op.drop_constraint(name, "purchase_order_items", type_="check")
    for name in ("ix_purchase_order_item_tenant_sq_item", "ix_purchase_order_item_tenant_mr_item"):
        op.drop_index(name, table_name="purchase_order_items")
    for name in ("fk_purchase_order_item_price", "fk_purchase_order_item_price_list", "fk_purchase_order_item_warehouse", "fk_purchase_order_item_uom", "fk_purchase_order_item_sq_item", "fk_purchase_order_item_rfq_item", "fk_purchase_order_item_mr_item"):
        op.drop_constraint(name, "purchase_order_items", type_="foreignkey")
    for column in ("stock_quantity", "conversion_factor", "price_list_rate", "item_price_id", "price_list_id", "target_warehouse_id", "uom_id", "supplier_quotation_item_id", "rfq_item_id", "material_request_item_id"):
        op.drop_column("purchase_order_items", column)
    for name in ("ck_purchase_order_discount_nonnegative", "ck_purchase_order_exchange_rate_positive"):
        op.drop_constraint(name, "purchase_orders", type_="check")
    op.drop_index("ix_purchase_order_tenant_material_request", table_name="purchase_orders")
    for name in ("fk_purchase_order_target_warehouse", "fk_purchase_order_shipping_rule", "fk_purchase_order_terms_template", "fk_purchase_order_shipping_address", "fk_purchase_order_supplier_address", "fk_purchase_order_supplier_contact", "fk_purchase_order_material_request"):
        op.drop_constraint(name, "purchase_orders", type_="foreignkey")
    for column in ("taxes_and_charges", "discount_amount", "target_warehouse_id", "exchange_rate", "shipping_rule_id", "incoterm", "payment_terms", "terms_text", "terms_template_id", "shipping_address_snapshot", "shipping_address_id", "supplier_address_snapshot", "supplier_address_id", "supplier_contact_snapshot", "supplier_contact_id", "material_request_id"):
        op.drop_column("purchase_orders", column)
