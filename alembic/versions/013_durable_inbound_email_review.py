"""Persist tenant-scoped inbound email intake and review state.

Revision ID: 013_durable_inbound_email_review
Revises: 012_approval_execution_outcomes
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_durable_inbound_email_review"
down_revision: str | None = "012_approval_execution_outcomes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    if "inbound_email_records" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "inbound_email_records",
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("attachment_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("associated_dag_id", sa.String(length=64), nullable=True),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.order_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "idx_inbound_email_tenant_status",
        "inbound_email_records",
        ["tenant_id", "status", "received_at"],
    )
    if "fulfillment_warehouse_id" not in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("sales_orders")
    }:
        op.add_column(
            "sales_orders",
            sa.Column("fulfillment_warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_sales_orders_fulfillment_warehouse",
            "sales_orders",
            "warehouses",
            ["fulfillment_warehouse_id"],
            ["warehouse_id"],
        )


def downgrade() -> None:
    if "inbound_email_records" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("idx_inbound_email_tenant_status", table_name="inbound_email_records")
    op.drop_table("inbound_email_records")
    if "fulfillment_warehouse_id" in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("sales_orders")
    }:
        op.drop_constraint("fk_sales_orders_fulfillment_warehouse", "sales_orders", type_="foreignkey")
        op.drop_column("sales_orders", "fulfillment_warehouse_id")
