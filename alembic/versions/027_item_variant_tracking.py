"""Add variant and serial/batch tracking fields to inventory items.

Revision ID: 027_item_variant_tracking
Revises: 026_saas_safepay_subscriptions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "027_item_variant_tracking"
down_revision: str | None = "026_saas_safepay_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("has_variants", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "items",
        sa.Column(
            "variant_of",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.item_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "items",
        sa.Column("variant_attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("has_batch_no", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "items",
        sa.Column("has_serial_no", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("items", "has_serial_no")
    op.drop_column("items", "has_batch_no")
    op.drop_column("items", "variant_attributes")
    op.drop_column("items", "variant_of")
    op.drop_column("items", "has_variants")
