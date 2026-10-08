"""Persist queryable event dead letters.

Revision ID: 011_event_dead_letters
Revises: 010_durable_event_processing
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_event_dead_letters"
down_revision: str | None = "010_durable_event_processing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "event_dead_letter_records" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "event_dead_letter_records",
        sa.Column("dead_letter_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consumer_group", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_topic", sa.String(length=249), nullable=False),
        sa.Column("partition_key", sa.String(length=512), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="OPEN"),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "consumer_group", "event_id", name="uq_event_dead_letter_group_event"
        ),
    )
    op.create_index(
        "idx_event_dead_letter_tenant_status",
        "event_dead_letter_records",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "event_dead_letter_records" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_event_dead_letter_tenant_status", table_name="event_dead_letter_records")
        op.drop_table("event_dead_letter_records")
