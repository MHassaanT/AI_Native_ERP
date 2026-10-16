"""Tenant subscriptions and idempotent SafePay webhook records."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TimestampMixin


class SaaSSubscription(Base, TimestampMixin):
    """A tenant's SaaS subscription, correlated to a SafePay plan and reference."""

    __tablename__ = "saas_subscriptions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    safepay_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="MONTH")
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_saas_subscriptions_tenant_created", "tenant_id", "created_at"),
        Index("idx_saas_subscriptions_status", "tenant_id", "status"),
    )


class SafePayWebhookEvent(Base):
    """Webhook inbox used to deduplicate and audit SafePay event deliveries."""

    __tablename__ = "safepay_webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

