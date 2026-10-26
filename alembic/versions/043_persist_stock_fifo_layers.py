"""Persist stock FIFO receipt layers and their outbound consumptions.

Revision ID: 043_persist_stock_fifo_layers
Revises: 042_receipt_uom_stock_snapshots
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "043_persist_stock_fifo_layers"
down_revision: str | None = "042_receipt_uom_stock_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "stock_valuation_layers",
        sa.Column("layer_id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("item_id", UUID, sa.ForeignKey("items.item_id"), nullable=False),
        sa.Column("warehouse_id", UUID, sa.ForeignKey("warehouses.warehouse_id"), nullable=False),
        sa.Column("source_entry_id", UUID, sa.ForeignKey("stock_ledger_entries.entry_id"), nullable=True),
        sa.Column("source_document_type", sa.String(64), nullable=False),
        sa.Column("source_document_id", UUID, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("remaining_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("received_qty > 0 AND remaining_qty >= 0 AND remaining_qty <= received_qty", name="ck_stock_layer_qty_valid"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_stock_layer_cost_nonnegative"),
    )
    op.create_index("ix_stock_fifo_tenant_item_wh_date", "stock_valuation_layers", ["tenant_id", "item_id", "warehouse_id", "received_at", "layer_id"])
    op.create_index("uq_stock_layer_source_entry", "stock_valuation_layers", ["tenant_id", "source_entry_id"], unique=True)
    op.create_table(
        "stock_layer_consumptions",
        sa.Column("consumption_id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("layer_id", UUID, sa.ForeignKey("stock_valuation_layers.layer_id"), nullable=False),
        sa.Column("outgoing_entry_id", UUID, sa.ForeignKey("stock_ledger_entries.entry_id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("is_reversed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("quantity > 0 AND unit_cost >= 0", name="ck_stock_layer_consumption_valid"),
    )
    op.create_index("ix_stock_layer_consumption_tenant_entry", "stock_layer_consumptions", ["tenant_id", "outgoing_entry_id"])
    op.create_index("uq_stock_layer_consumption_pair", "stock_layer_consumptions", ["tenant_id", "outgoing_entry_id", "layer_id"], unique=True)
    # Seed an opening FIFO layer for existing positive stock. This records a
    # transparent estimated cost basis and ensures stock already on hand remains
    # fulfillable immediately after enabling strict layer consumption.
    op.execute(sa.text("""
        INSERT INTO stock_valuation_layers
            (layer_id, tenant_id, item_id, warehouse_id, source_document_type,
             received_at, received_qty, remaining_qty, unit_cost, is_cancelled)
        SELECT gen_random_uuid(), tenant_id, item_id, warehouse_id, 'OPENING_BALANCE',
               COALESCE(created_at, now()), current_qty, current_qty,
               GREATEST(valuation_rate, 0), false
        FROM stock_levels
        WHERE current_qty > 0
    """))
    op.execute(sa.text("""
        CREATE FUNCTION erp_apply_stock_fifo_layer() RETURNS trigger AS $$
        DECLARE
            fifo_layer RECORD;
            qty_left NUMERIC(18, 4);
            qty_taken NUMERIC(18, 4);
            total_cost NUMERIC(24, 8) := 0;
            layer_cost NUMERIC(18, 4);
        BEGIN
            IF NEW.is_cancelled THEN
                RETURN NEW;
            END IF;
            IF NEW.actual_qty > 0 THEN
                INSERT INTO stock_valuation_layers
                    (layer_id, tenant_id, item_id, warehouse_id, source_entry_id,
                     source_document_type, source_document_id, received_at,
                     received_qty, remaining_qty, unit_cost, is_cancelled)
                VALUES
                    (gen_random_uuid(), NEW.tenant_id, NEW.item_id, NEW.warehouse_id,
                     NEW.entry_id, NEW.source_document_type, NEW.source_document_id,
                     NEW.posting_datetime, NEW.actual_qty, NEW.actual_qty,
                     GREATEST(COALESCE(NULLIF(NEW.incoming_rate, 0), NEW.valuation_rate), 0), false);
            ELSIF NEW.actual_qty < 0 THEN
                qty_left := abs(NEW.actual_qty);
                FOR fifo_layer IN
                    SELECT * FROM stock_valuation_layers
                    WHERE tenant_id = NEW.tenant_id AND item_id = NEW.item_id
                      AND warehouse_id = NEW.warehouse_id AND is_cancelled = false
                      AND remaining_qty > 0
                    ORDER BY received_at, layer_id
                    FOR UPDATE
                LOOP
                    EXIT WHEN qty_left <= 0;
                    qty_taken := LEAST(fifo_layer.remaining_qty, qty_left);
                    layer_cost := fifo_layer.unit_cost;
                    UPDATE stock_valuation_layers
                    SET remaining_qty = remaining_qty - qty_taken
                    WHERE layer_id = fifo_layer.layer_id;
                    INSERT INTO stock_layer_consumptions
                        (consumption_id, tenant_id, layer_id, outgoing_entry_id, quantity, unit_cost, is_reversed)
                    VALUES
                        (gen_random_uuid(), NEW.tenant_id, fifo_layer.layer_id, NEW.entry_id, qty_taken, layer_cost, false);
                    total_cost := total_cost + qty_taken * layer_cost;
                    qty_left := qty_left - qty_taken;
                END LOOP;
                IF qty_left > 0 THEN
                    RAISE EXCEPTION 'Insufficient FIFO layers for stock ledger entry %, short by % units', NEW.entry_id, qty_left;
                END IF;
                UPDATE stock_ledger_entries
                SET outgoing_rate = round(total_cost / abs(NEW.actual_qty), 4),
                    stock_value_difference = -round(total_cost, 4)
                WHERE entry_id = NEW.entry_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_stock_ledger_fifo_layer
        AFTER INSERT ON stock_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION erp_apply_stock_fifo_layer()
    """))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_stock_ledger_fifo_layer ON stock_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS erp_apply_stock_fifo_layer()")
    op.drop_index("uq_stock_layer_consumption_pair", table_name="stock_layer_consumptions")
    op.drop_index("ix_stock_layer_consumption_tenant_entry", table_name="stock_layer_consumptions")
    op.drop_table("stock_layer_consumptions")
    op.drop_index("ix_stock_fifo_tenant_item_wh_date", table_name="stock_valuation_layers")
    op.drop_index("uq_stock_layer_source_entry", table_name="stock_valuation_layers")
    op.drop_table("stock_valuation_layers")
