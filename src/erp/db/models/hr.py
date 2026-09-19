"""Workforce and Human Resources Domain Models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

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
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Employee(Base, TenantMixin, TimestampMixin):
    """Employee record with certifications and labor constraints."""

    __tablename__ = "employees"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_code: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    certifications: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        doc="Active verified safety and machine operational certifications",
    )
    max_weekly_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=48, doc="Statutory labor law ceiling"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_emp_tenant_code", "tenant_id", "employee_code", unique=True),)


class ShiftSchedule(Base, TenantMixin, TimestampMixin):
    """Factory shift roster."""

    __tablename__ = "shift_schedules"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_code: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SCHEDULED",  # SCHEDULED, SWAP_REQUESTED, COMPLETED, CANCELLED
    )

    __table_args__ = (Index("idx_shift_tenant_emp_date", "tenant_id", "employee_id", "shift_date"),)


class ExpenseClaim(Base, TenantMixin, TimestampMixin):
    """Employee travel and operational expense claims."""

    __tablename__ = "expense_claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="MEALS",  # MEALS, LODGING, TRANSPORT, SUPPLIES
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    receipt_image_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="SHA-256 deduplication hash"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SUBMITTED",  # SUBMITTED, AUTO_APPROVED, FLAGGED, PAID
    )
    auto_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    violation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_exp_tenant_number", "tenant_id", "claim_number", unique=True),)
