"""Record authorized DAG recovery requests.

Revision ID: 009_dag_recovery_audit
Revises: 008_customer_payment_terms
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_dag_recovery_audit"
down_revision: str | None = "008_customer_payment_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "dag_execution_records" not in sa.inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("dag_execution_records")}
    if "recovery_requested_by" not in columns:
        op.add_column(
            "dag_execution_records",
            sa.Column(
                "recovery_requested_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.user_id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "recovery_notes" not in columns:
        op.add_column("dag_execution_records", sa.Column("recovery_notes", sa.Text(), nullable=True))
    if "recovery_started_at" not in columns:
        op.add_column(
            "dag_execution_records",
            sa.Column("recovery_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "dag_execution_records" not in sa.inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("dag_execution_records")}
    for column_name in ("recovery_started_at", "recovery_notes", "recovery_requested_by"):
        if column_name in columns:
            op.drop_column("dag_execution_records", column_name)
