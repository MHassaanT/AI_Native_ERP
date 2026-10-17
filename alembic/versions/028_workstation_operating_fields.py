"""Add workstation operating fields required by the manufacturing ORM.

Revision ID: 028_workstation_operating_fields
Revises: 027_item_variant_tracking
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "028_workstation_operating_fields"
down_revision: str | None = "027_item_variant_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workstations",
        sa.Column(
            "workstation_type",
            sa.String(length=64),
            server_default="GENERAL",
            nullable=False,
        ),
    )
    op.add_column(
        "workstations",
        sa.Column(
            "production_capacity",
            sa.Numeric(precision=18, scale=4),
            server_default="1.0000",
            nullable=False,
        ),
    )
    op.add_column(
        "workstations",
        sa.Column(
            "electricity_cost_per_hour",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
    )
    op.add_column(
        "workstations",
        sa.Column(
            "consumable_cost_per_hour",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
    )
    op.add_column(
        "workstations",
        sa.Column(
            "rent_per_hour",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("workstations", "rent_per_hour")
    op.drop_column("workstations", "consumable_cost_per_hour")
    op.drop_column("workstations", "electricity_cost_per_hour")
    op.drop_column("workstations", "production_capacity")
    op.drop_column("workstations", "workstation_type")
