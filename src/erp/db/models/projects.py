"""Project, Task, and Timesheet Tracking Domain Models (ERPNext Parity)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Project(Base, TenantMixin, TimestampMixin):
    """Master project record tracking budgets, schedules, milestones, and actual billing."""

    __tablename__ = "projects"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    actual_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_billed_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    percent_complete: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="IN_PROGRESS"  # PLANNING, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tasks: Mapped[List["ProjectTask"]] = relationship(
        "ProjectTask", back_populates="project", cascade="all, delete-orphan"
    )
    timesheets: Mapped[List["Timesheet"]] = relationship(
        "Timesheet", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_proj_tenant_code", "tenant_id", "project_code", unique=True),
        Index("idx_proj_tenant_status", "tenant_id", "status"),
    )


class ProjectTask(Base, TenantMixin, TimestampMixin):
    """Discrete task work item assigned to employee with deadline and hours estimate."""

    __tablename__ = "project_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    task_title: Mapped[str] = mapped_column(String(255), nullable=False)
    task_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MEDIUM"  # LOW, MEDIUM, HIGH, URGENT
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"  # OPEN, WORKING, PENDING_REVIEW, COMPLETED
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    actual_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, doc="Employee ID assigned"
    )
    assigned_to_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    timesheets: Mapped[List["Timesheet"]] = relationship(
        "Timesheet", back_populates="task"
    )

    __table_args__ = (
        Index("idx_ptask_tenant_proj", "tenant_id", "project_id"),
    )


class Timesheet(Base, TenantMixin, TimestampMixin):
    """Detailed employee labor timesheet tracking billable/costed hours."""

    __tablename__ = "timesheets"

    timesheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timesheet_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    employee_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_tasks.task_id"), nullable=True, index=True
    )
    activity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="ENGINEERING"  # CONSULTING, ENGINEERING, FABRICATION, SUPPORT
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("1.00")
    )
    billing_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("100.0000")
    )
    costing_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("50.0000")
    )
    billing_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("100.0000")
    )
    costing_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("50.0000")
    )
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SUBMITTED"  # DRAFT, SUBMITTED, BILLED
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="timesheets")
    task: Mapped[Optional["ProjectTask"]] = relationship("ProjectTask", back_populates="timesheets")

    __table_args__ = (
        Index("idx_ts_tenant_num", "tenant_id", "timesheet_number", unique=True),
        Index("idx_ts_tenant_emp", "tenant_id", "employee_id"),
    )
