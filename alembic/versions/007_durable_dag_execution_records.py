"""Persist tenant-scoped DAG execution snapshots.

Revision ID: 007_dag_execution_records
Revises: 006_phase_1_billing
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_dag_execution_records"
down_revision: str | None = "006_phase_1_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "dag_execution_records" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "dag_execution_records",
        sa.Column("dag_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DISPATCHED"),
        sa.Column("workflow_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recovery_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False
        ),
    )
    op.create_index(
        "idx_dag_execution_tenant_status",
        "dag_execution_records",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "dag_execution_records" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_dag_execution_tenant_status", table_name="dag_execution_records")
        op.drop_table("dag_execution_records")
