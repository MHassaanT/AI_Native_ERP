"""Preventive Maintenance and Technician Service Domain Models (ERPNext Parity)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class MaintenanceSchedule(Base, TenantMixin, TimestampMixin):
    """Recurring preventive maintenance schedule for machinery, assets, or tooling."""

    __tablename__ = "maintenance_schedules"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=True, index=True
    )
    item_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    periodicity: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MONTHLY"  # WEEKLY, MONTHLY, QUARTERLY, ANNUAL
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_items: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, doc="JSON array of inspection checklist task strings"
    )
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"  # ACTIVE, PAUSED, EXPIRED
    )

    visits: Mapped[List["MaintenanceVisit"]] = relationship(
        "MaintenanceVisit", back_populates="schedule", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_ms_tenant_num", "tenant_id", "schedule_number", unique=True),
        Index("idx_ms_tenant_status", "tenant_id", "status"),
    )


class MaintenanceVisit(Base, TenantMixin, TimestampMixin):
    """Execution record for an on-site or shop technician maintenance visit."""

    __tablename__ = "maintenance_visits"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    visit_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_schedules.schedule_id"), nullable=True, index=True
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=True, index=True
    )
    technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, doc="Employee ID of assigned technician"
    )
    technician_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    maintenance_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PREVENTIVE"  # PREVENTIVE, BREAKDOWN
    )
    tasks_performed: Mapped[str] = mapped_column(Text, nullable=False)
    parts_replaced: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    downtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    maintenance_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="COMPLETED"  # SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
    )

    schedule: Mapped[Optional["MaintenanceSchedule"]] = relationship(
        "MaintenanceSchedule", back_populates="visits"
    )

    __table_args__ = (
        Index("idx_mv_tenant_num", "tenant_id", "visit_number", unique=True),
    )
