"""Tenant Settings and Onboarding Progress Domain Models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class TenantSettings(Base, TenantMixin, TimestampMixin):
    """Configurable system settings per tenant."""

    __tablename__ = "tenant_settings"

    setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    valuation_method: Mapped[str] = mapped_column(String(32), nullable=False, default="FIFO")
    default_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.warehouse_id", ondelete="SET NULL"),
        nullable=True,
    )
    default_buying_price_list: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Standard Buying"
    )
    default_selling_price_list: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Standard Selling"
    )
    stock_uom: Mapped[str] = mapped_column(String(32), nullable=False, default="Nos")
    date_format: Mapped[str] = mapped_column(String(32), nullable=False, default="YYYY-MM-DD")
    number_format: Mapped[str] = mapped_column(String(32), nullable=False, default="#,###.##")
    margin_floor_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("22.00")
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")  # type: ignore[name-defined] # noqa: F821


class OnboardingProgress(Base, TenantMixin, TimestampMixin):
    """Tracks module-level onboarding completion status."""

    __tablename__ = "onboarding_progress"

    progress_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_slug", name="uq_tenant_module_progress"),
        Index("idx_onboarding_progress_tenant", "tenant_id", "module_slug"),
    )


class OnboardingStep(Base, TenantMixin, TimestampMixin):
    """Individual action/verification step within a module onboarding checklist."""

    __tablename__ = "onboarding_steps"

    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    step_title: Mapped[str] = mapped_column(String(255), nullable=False)
    step_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="CREATE_ENTRY",  # CREATE_ENTRY, VIEW_REPORT, CONFIGURE_SETTING, VIEW_DOCS
    )
    reference_entity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_slug", "step_key", name="uq_tenant_module_step"),
        Index("idx_onboarding_step_tenant_module", "tenant_id", "module_slug", "step_key"),
    )
