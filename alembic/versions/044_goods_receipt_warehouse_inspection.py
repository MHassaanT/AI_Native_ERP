"""Persist receipt warehouse and inspection completion per line.

Revision ID: 044_goods_receipt_warehouse_inspection
Revises: 043_persist_stock_fifo_layers
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "044_goods_receipt_warehouse_inspection"
down_revision: str | None = "043_persist_stock_fifo_layers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("goods_receipt_note_items", sa.Column("warehouse_id", UUID, nullable=True))
    op.add_column("goods_receipt_note_items", sa.Column("inspection_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_grn_item_warehouse", "goods_receipt_note_items", "warehouses", ["warehouse_id"], ["warehouse_id"])
    op.execute(sa.text("""
        UPDATE goods_receipt_note_items AS gri
        SET warehouse_id = sle.warehouse_id
        FROM stock_ledger_entries AS sle
        WHERE sle.tenant_id = gri.tenant_id
          AND sle.source_document_type = 'GOODS_RECEIPT'
          AND sle.source_document_id = gri.grn_id
          AND sle.item_id = gri.item_id
          AND sle.actual_qty > 0
    """))
    op.alter_column("goods_receipt_note_items", "inspection_completed", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_grn_item_warehouse", "goods_receipt_note_items", type_="foreignkey")
    op.drop_column("goods_receipt_note_items", "inspection_completed")
    op.drop_column("goods_receipt_note_items", "warehouse_id")
