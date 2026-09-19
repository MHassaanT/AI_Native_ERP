"""Manufacturing and Shop-Floor Domain Models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Workstation(Base, TenantMixin, TimestampMixin):
    """Factory machine or assembly station registry."""

    __tablename__ = "workstations"

    workstation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workstation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    workstation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="OPERATIONAL",  # OPERATIONAL, MAINTENANCE, FAULT, IDLE
    )
    iot_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    health_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_ws_tenant_code", "tenant_id", "workstation_code", unique=True),)


class BOM(Base, TenantMixin, TimestampMixin):
    """Bill of Materials specifying component formulas."""

    __tablename__ = "boms"

    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_number: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["BOMItem"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_bom_tenant_number", "tenant_id", "bom_number", unique=True),)


class BOMItem(Base, TenantMixin, TimestampMixin):
    """Component line in Bill of Materials."""

    __tablename__ = "bom_items"

    bom_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    bom: Mapped["BOM"] = relationship(back_populates="items")


class WorkOrder(Base, TenantMixin, TimestampMixin):
    """Production Work Order."""

    __tablename__ = "work_orders"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    bom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=True
    )
    workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    produced_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    planned_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
    )

    __table_args__ = (Index("idx_wo_tenant_number", "tenant_id", "work_order_number", unique=True),)


class MaintenanceTicket(Base, TenantMixin, TimestampMixin):
    """Predictive or corrective equipment maintenance ticket."""

    __tablename__ = "maintenance_tickets"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_number: Mapped[str] = mapped_column(String(64), nullable=False)
    workstation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PREDICTIVE_ANOMALY",  # PREDICTIVE_ANOMALY, MANUAL, SCHEDULED
    )
    fault_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="OPEN",  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    )

    __table_args__ = (Index("idx_maint_tenant_number", "tenant_id", "ticket_number", unique=True),)
