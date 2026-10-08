"""Persist approval action execution outcomes.

Revision ID: 012_approval_execution_outcomes
Revises: 011_event_dead_letters
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_approval_execution_outcomes"
down_revision: str | None = "011_event_dead_letters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "agent_approvals" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_approvals")}
    if "action_execution_status" not in columns:
        op.add_column(
            "agent_approvals",
            sa.Column("action_execution_status", sa.String(length=24), nullable=False, server_default="NOT_STARTED"),
        )
        op.execute(
            "UPDATE agent_approvals SET action_execution_status = CASE "
            "WHEN status IN ('APPROVED', 'MODIFIED') THEN 'UNKNOWN' ELSE 'NOT_STARTED' END"
        )
    if "action_execution_result" not in columns:
        op.add_column(
            "agent_approvals",
            sa.Column("action_execution_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "agent_approvals" not in sa.inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_approvals")}
    for column_name in ("action_execution_result", "action_execution_status"):
        if column_name in columns:
            op.drop_column("agent_approvals", column_name)
