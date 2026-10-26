"""Persist POS cost snapshots and link return lines to sold lines.

Revision ID: 056_pos_cost_and_return_lineage
Revises: 055_customer_advance_ledger
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "056_pos_cost_and_return_lineage"
down_revision: str | None = "055_customer_advance_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pos_invoice_items", sa.Column("source_pos_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_pos_invoice_item_source_pos_item", "pos_invoice_items", "pos_invoice_items",
        ["source_pos_item_id"], ["pos_item_id"],
    )
    op.add_column("pos_invoice_items", sa.Column("cost_unit_stock", sa.Numeric(18, 4), nullable=True))
    op.add_column("pos_invoice_items", sa.Column("cost_amount", sa.Numeric(18, 4), nullable=True))
    op.add_column("pos_invoice_items", sa.Column("cost_valuation_method", sa.String(32), nullable=True))
    op.add_column("pos_invoice_items", sa.Column("cost_source", sa.String(48), nullable=True))
    op.add_column("pos_invoice_items", sa.Column(
        "cost_is_estimated", sa.Boolean(), nullable=False, server_default=sa.true()
    ))


def downgrade() -> None:
    op.drop_column("pos_invoice_items", "cost_is_estimated")
    op.drop_column("pos_invoice_items", "cost_source")
    op.drop_column("pos_invoice_items", "cost_valuation_method")
    op.drop_column("pos_invoice_items", "cost_amount")
    op.drop_column("pos_invoice_items", "cost_unit_stock")
    op.drop_constraint("fk_pos_invoice_item_source_pos_item", "pos_invoice_items", type_="foreignkey")
    op.drop_column("pos_invoice_items", "source_pos_item_id")
