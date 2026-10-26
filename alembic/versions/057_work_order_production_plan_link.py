"""Add the missing production-plan link to work orders.

Revision ID: 057_work_order_production_plan_link
Revises: 056_pos_cost_and_return_lineage
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "057_work_order_production_plan_link"
down_revision: str | None = "056_pos_cost_and_return_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_orders",
        sa.Column("production_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_work_order_production_plan",
        "work_orders",
        "production_plans",
        ["production_plan_id"],
        ["plan_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_work_order_production_plan", "work_orders", type_="foreignkey",
    )
    op.drop_column("work_orders", "production_plan_id")
