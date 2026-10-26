"""Persist purchase UOM conversion on goods receipt lines.

Revision ID: 042_receipt_uom_stock_snapshots
Revises: 041_commercial_tax_snapshots
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "042_receipt_uom_stock_snapshots"
down_revision: str | None = "041_commercial_tax_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("goods_receipt_note_items", sa.Column(
        "conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"
    ))
    op.add_column("goods_receipt_note_items", sa.Column(
        "stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"
    ))
    op.execute("UPDATE goods_receipt_note_items SET stock_quantity = quantity_received")
    op.create_check_constraint(
        "ck_grn_item_conversion_positive", "goods_receipt_note_items", "conversion_factor > 0"
    )
    op.create_check_constraint(
        "ck_grn_item_stock_quantity_nonnegative", "goods_receipt_note_items", "stock_quantity >= 0"
    )
    op.alter_column("goods_receipt_note_items", "conversion_factor", server_default=None)
    op.alter_column("goods_receipt_note_items", "stock_quantity", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_grn_item_stock_quantity_nonnegative", "goods_receipt_note_items", type_="check")
    op.drop_constraint("ck_grn_item_conversion_positive", "goods_receipt_note_items", type_="check")
    op.drop_column("goods_receipt_note_items", "stock_quantity")
    op.drop_column("goods_receipt_note_items", "conversion_factor")
