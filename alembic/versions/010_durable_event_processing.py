"""Track durable Kafka event handling state.

Revision ID: 010_durable_event_processing
Revises: 009_dag_recovery_audit
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_durable_event_processing"
down_revision: str | None = "009_dag_recovery_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "event_processing_records" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "event_processing_records",
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consumer_group", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_topic", sa.String(length=249), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="RETRYABLE"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failure_type", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processing_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "received_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("consumer_group", "event_id", name="uq_event_processing_group_event"),
    )
    op.create_index(
        "idx_event_processing_status_updated",
        "event_processing_records",
        ["status", "updated_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "event_processing_records" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_event_processing_status_updated", table_name="event_processing_records")
        op.drop_table("event_processing_records")
