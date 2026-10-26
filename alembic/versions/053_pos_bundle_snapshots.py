"""Persist immutable product-bundle components on POS receipt lines.

Revision ID: 053_pos_bundle_snapshots
Revises: 052_pos_commercial_snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "053_pos_bundle_snapshots"
down_revision = "052_pos_commercial_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_invoice_items",
        sa.Column("bundle_components_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pos_invoice_items", "bundle_components_snapshot")
