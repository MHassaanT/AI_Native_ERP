"""003 Complete Business Cycles Schema (GRN items, Supplier Invoice items, Delivery Notes, Sales Invoices)

Revision ID: 003_complete_business_cycles
Revises: 002_multi_tenant_auth_and_certs
Create Date: 2026-09-19 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_complete_business_cycles"
down_revision: str | None = "002_multi_tenant_auth_and_certs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Goods Receipt Note Items
    if "goods_receipt_note_items" not in existing_tables:
        op.create_table(
            "goods_receipt_note_items",
            sa.Column(
                "grn_item_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "grn_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("goods_receipt_notes.grn_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "po_item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("purchase_order_items.item_line_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("items.item_id"),
                nullable=False,
            ),
            sa.Column("quantity_received", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column(
                "unit_price",
                sa.Numeric(precision=18, scale=4),
                server_default="0.0000",
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index("idx_grni_tenant_grn", "goods_receipt_note_items", ["tenant_id", "grn_id"])

    # 2. Supplier Invoice Items
    if "supplier_invoice_items" not in existing_tables:
        op.create_table(
            "supplier_invoice_items",
            sa.Column(
                "invoice_item_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "invoice_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("supplier_invoices.invoice_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("items.item_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("item_code", sa.String(length=64), nullable=False),
            sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("line_total", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index("idx_sii_tenant_inv", "supplier_invoice_items", ["tenant_id", "invoice_id"])

    # 3. Delivery Notes
    if "delivery_notes" not in existing_tables:
        op.create_table(
            "delivery_notes",
            sa.Column(
                "delivery_note_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("delivery_note_number", sa.String(length=64), nullable=False),
            sa.Column(
                "order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("sales_orders.order_id"),
                nullable=False,
            ),
            sa.Column(
                "customer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("customers.customer_id"),
                nullable=False,
            ),
            sa.Column("delivery_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="DISPATCHED", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_dn_tenant_number", "delivery_notes", ["tenant_id", "delivery_note_number"], unique=True
        )

    # 4. Delivery Note Items
    if "delivery_note_items" not in existing_tables:
        op.create_table(
            "delivery_note_items",
            sa.Column(
                "dn_item_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "delivery_note_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("delivery_notes.delivery_note_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "order_item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("sales_order_items.order_item_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("items.item_id"),
                nullable=False,
            ),
            sa.Column(
                "warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("warehouses.warehouse_id"),
                nullable=False,
            ),
            sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_dni_tenant_dn", "delivery_note_items", ["tenant_id", "delivery_note_id"]
        )

    # 5. Sales Invoices
    if "sales_invoices" not in existing_tables:
        op.create_table(
            "sales_invoices",
            sa.Column(
                "invoice_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("invoice_number", sa.String(length=64), nullable=False),
            sa.Column(
                "customer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("customers.customer_id"),
                nullable=False,
            ),
            sa.Column(
                "order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("sales_orders.order_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "delivery_note_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("delivery_notes.delivery_note_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("invoice_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
            sa.Column("subtotal", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column(
                "tax_amount",
                sa.Numeric(precision=18, scale=4),
                server_default="0.0000",
                nullable=False,
            ),
            sa.Column("total_amount", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="ISSUED", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_sinv_cust_number", "sales_invoices", ["tenant_id", "invoice_number"], unique=True
        )

    # 6. Sales Invoice Items
    if "sales_invoice_items" not in existing_tables:
        op.create_table(
            "sales_invoice_items",
            sa.Column(
                "invoice_item_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "invoice_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("sales_invoices.invoice_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("items.item_id"),
                nullable=False,
            ),
            sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column("line_total", sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index("idx_sinvi_tenant_inv", "sales_invoice_items", ["tenant_id", "invoice_id"])

    # 7. Add lot_number and is_quarantined columns to inventory tables if missing
    sle_cols = [c["name"] for c in inspector.get_columns("stock_ledger_entries")]
    if "lot_number" not in sle_cols:
        op.add_column("stock_ledger_entries", sa.Column("lot_number", sa.String(length=64), nullable=True))

    sl_cols = [c["name"] for c in inspector.get_columns("stock_levels")]
    if "lot_number" not in sl_cols:
        op.add_column("stock_levels", sa.Column("lot_number", sa.String(length=64), nullable=True))
    if "is_quarantined" not in sl_cols:
        op.add_column(
            "stock_levels",
            sa.Column("is_quarantined", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("sales_invoice_items")
    op.drop_table("sales_invoices")
    op.drop_table("delivery_note_items")
    op.drop_table("delivery_notes")
    op.drop_table("supplier_invoice_items")
    op.drop_table("goods_receipt_note_items")
