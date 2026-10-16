"""Add tenant SaaS subscription state and SafePay webhook inbox.

Revision ID: 026_saas_safepay_subscriptions
Revises: 025_add_missing_employee_columns
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "026_saas_safepay_subscriptions"
down_revision: str | None = "025_add_missing_employee_columns"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "saas_subscriptions",
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_name", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=False),
        sa.Column("safepay_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("billing_interval", sa.String(length=16), server_default="MONTH", nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id"),
        sa.UniqueConstraint("reference", name="uq_saas_subscriptions_reference"),
    )
    op.create_index(
        "idx_saas_subscriptions_tenant_created",
        "saas_subscriptions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_saas_subscriptions_status", "saas_subscriptions", ["tenant_id", "status"]
    )
    op.create_table(
        "safepay_webhook_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("safepay_webhook_events")
    op.drop_index("idx_saas_subscriptions_status", table_name="saas_subscriptions")
    op.drop_index("idx_saas_subscriptions_tenant_created", table_name="saas_subscriptions")
    op.drop_table("saas_subscriptions")
