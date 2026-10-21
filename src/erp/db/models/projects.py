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
    project_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_types.project_type_id"), nullable=True
    )
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
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_update_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tasks: Mapped[List["ProjectTask"]] = relationship(
        "ProjectTask", back_populates="project", cascade="all, delete-orphan"
    )
    timesheets: Mapped[List["Timesheet"]] = relationship(
        "Timesheet", back_populates="project", cascade="all, delete-orphan"
    )
    updates: Mapped[List["ProjectUpdate"]] = relationship(
        "ProjectUpdate", back_populates="project", cascade="all, delete-orphan"
    )
    project_type = relationship("ProjectType")

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
    activity_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_types.activity_type_id"), nullable=True
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


class ProjectUpdate(Base, TenantMixin, TimestampMixin):
    """Historical progress update logged for a project via email or manual report."""

    __tablename__ = "project_updates"

    update_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    progress_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="updates")

    __table_args__ = (
        Index("idx_proj_updates_tenant_proj", "tenant_id", "project_id", "created_at"),
    )


class ProjectType(Base, TenantMixin, TimestampMixin):
    __tablename__ = "project_types"
    project_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (Index("uq_project_type_tenant_name", "tenant_id", "type_name", unique=True),)


class ActivityType(Base, TenantMixin, TimestampMixin):
    __tablename__ = "activity_types"
    activity_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (Index("uq_activity_type_tenant_name", "tenant_id", "activity_name", unique=True),)


class ActivityCost(Base, TenantMixin, TimestampMixin):
    """Effective-dated activity rates optionally scoped to one employee."""
    __tablename__ = "activity_costs"
    activity_cost_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("activity_types.activity_type_id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True)
    billing_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    costing_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    activity_type = relationship("ActivityType")
    __table_args__ = (Index("idx_activity_cost_tenant_type_employee", "tenant_id", "activity_type_id", "employee_id", "valid_from"),)

