"""Add optional ledger reporting dimensions and purpose.

Revision ID: 058_ledger_reporting_details
Revises: 057_work_order_production_plan_link
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "058_ledger_reporting_details"
down_revision = "057_work_order_production_plan_link"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("general_ledger_entries", sa.Column("purpose", sa.String(1000), nullable=True))
    op.add_column("general_ledger_entries", sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("general_ledger_entries", sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade():
    for column in ("item_id", "warehouse_id", "purpose"):
        op.drop_column("general_ledger_entries", column)
