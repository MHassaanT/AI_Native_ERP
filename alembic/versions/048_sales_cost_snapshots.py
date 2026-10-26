"""Persist delivery, invoice and return cost snapshots for gross profit.

Revision ID: 048_sales_cost_snapshots
Revises: 047_party_ledger_dimensions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "048_sales_cost_snapshots"
down_revision = "047_party_ledger_dimensions"
branch_labels = None
depends_on = None


def _add_cost_columns(table: str, include_conversion: bool = False) -> None:
    if include_conversion:
        op.add_column(table, sa.Column("conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"))
        op.add_column(table, sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"))
    else:
        op.add_column(table, sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=True))
    op.add_column(table, sa.Column("cost_unit_stock", sa.Numeric(18, 4), nullable=True))
    op.add_column(table, sa.Column("cost_amount", sa.Numeric(18, 4), nullable=True))
    op.add_column(table, sa.Column("cost_valuation_method", sa.String(32), nullable=True))
    op.add_column(table, sa.Column("cost_source", sa.String(48), nullable=True))
    if table != "credit_note_items":
        op.add_column(table, sa.Column("cost_source_entry_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table, sa.Column("cost_is_estimated", sa.Boolean(), nullable=False, server_default=sa.true()))


def upgrade() -> None:
    _add_cost_columns("delivery_note_items", include_conversion=True)
    _add_cost_columns("sales_invoice_items")
    _add_cost_columns("credit_note_items")

    # Keep pre-existing delivery valuation when available. Old rows that only
    # have a current master rate are explicitly marked as estimates.
    op.execute(sa.text("""
        WITH legacy_costs AS (
            SELECT d.dn_item_id,
                   COALESCE(soi.conversion_factor, 1) AS conversion_factor,
                   COALESCE(NULLIF(sle.valuation_rate, 0), i.standard_rate, 0) AS unit_cost,
                   i.valuation_method,
                   sle.entry_id AS source_entry_id,
                   NULLIF(sle.valuation_rate, 0) IS NULL AS estimated
            FROM delivery_note_items d
            JOIN delivery_notes dn ON dn.delivery_note_id = d.delivery_note_id
                                  AND dn.tenant_id = d.tenant_id
            LEFT JOIN sales_order_items soi ON soi.order_item_id = d.order_item_id
                                            AND soi.tenant_id = d.tenant_id
            JOIN items i ON i.item_id = d.item_id AND i.tenant_id = d.tenant_id
            LEFT JOIN LATERAL (
                SELECT s.entry_id, s.valuation_rate
                FROM stock_ledger_entries s
                WHERE s.tenant_id = d.tenant_id AND s.source_document_type = 'DELIVERY_NOTE'
                  AND s.source_document_id = d.delivery_note_id AND s.item_id = d.item_id
                  AND s.actual_qty < 0 AND s.is_cancelled IS FALSE
                ORDER BY s.posting_datetime DESC, s.entry_id DESC LIMIT 1
            ) sle ON TRUE
        )
        UPDATE delivery_note_items d
        SET conversion_factor = c.conversion_factor,
            stock_quantity = d.quantity * c.conversion_factor,
            cost_unit_stock = c.unit_cost,
            cost_amount = d.quantity * c.conversion_factor * c.unit_cost,
            cost_valuation_method = c.valuation_method,
            cost_source = CASE WHEN c.estimated THEN 'LEGACY_ITEM_RATE' ELSE 'LEGACY_STOCK_LEDGER' END,
            cost_source_entry_id = c.source_entry_id,
            cost_is_estimated = c.estimated
        FROM legacy_costs c
        WHERE d.dn_item_id = c.dn_item_id
    """))

    op.execute(sa.text("""
        WITH invoice_costs AS (
            SELECT si.invoice_item_id,
                   COALESCE(d.stock_quantity, si.quantity * COALESCE(soi.conversion_factor, 1)) AS stock_quantity,
                   COALESCE(d.cost_unit_stock, i.standard_rate, 0) AS unit_cost,
                   COALESCE(d.cost_amount,
                       si.quantity * COALESCE(soi.conversion_factor, 1) * COALESCE(i.standard_rate, 0)) AS cost_amount,
                   COALESCE(d.cost_valuation_method, i.valuation_method) AS valuation_method,
                   COALESCE(d.cost_source, 'LEGACY_ITEM_RATE') AS cost_source,
                   d.cost_source_entry_id AS source_entry_id,
                   COALESCE(d.cost_is_estimated, TRUE) AS estimated
            FROM sales_invoice_items si
            JOIN items i ON i.item_id = si.item_id AND i.tenant_id = si.tenant_id
            LEFT JOIN sales_order_items soi ON soi.order_item_id = si.order_item_id AND soi.tenant_id = si.tenant_id
            LEFT JOIN delivery_note_items d ON d.dn_item_id = si.delivery_note_item_id AND d.tenant_id = si.tenant_id
        )
        UPDATE sales_invoice_items si
        SET stock_quantity = c.stock_quantity,
            cost_unit_stock = c.unit_cost,
            cost_amount = c.cost_amount,
            cost_valuation_method = c.valuation_method,
            cost_source = c.cost_source,
            cost_source_entry_id = c.source_entry_id,
            cost_is_estimated = c.estimated
        FROM invoice_costs c
        WHERE si.invoice_item_id = c.invoice_item_id
    """))

    op.execute(sa.text("""
        UPDATE credit_note_items cn
        SET stock_quantity = CASE WHEN si.quantity > 0 THEN cn.quantity * si.stock_quantity / si.quantity END,
            cost_unit_stock = si.cost_unit_stock,
            cost_amount = CASE WHEN si.quantity > 0 THEN cn.quantity * si.cost_amount / si.quantity END,
            cost_valuation_method = si.cost_valuation_method,
            cost_source = si.cost_source,
            cost_is_estimated = COALESCE(si.cost_is_estimated, TRUE)
        FROM sales_invoice_items si
        WHERE cn.sales_invoice_item_id = si.invoice_item_id AND cn.tenant_id = si.tenant_id
    """))


def downgrade() -> None:
    for table in ("credit_note_items", "sales_invoice_items", "delivery_note_items"):
        columns = ["cost_is_estimated", "cost_source"]
        if table != "credit_note_items":
            columns.append("cost_source_entry_id")
        columns.extend(["cost_valuation_method", "cost_amount", "cost_unit_stock", "stock_quantity"])
        if table == "delivery_note_items":
            columns.append("conversion_factor")
        for name in columns:
            op.drop_column(table, name)
