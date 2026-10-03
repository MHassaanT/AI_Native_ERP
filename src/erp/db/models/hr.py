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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Department(Base, TenantMixin, TimestampMixin):
    """Organizational business units and reporting hierarchy."""

    __tablename__ = "departments"

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    department_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True
    )
    department_head_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_dept_tenant_name", "tenant_id", "department_name", unique=True),
    )


class Designation(Base, TenantMixin, TimestampMixin):
    """Job titles and functional designations."""

    __tablename__ = "designations"

    designation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    designation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_desig_tenant_name", "tenant_id", "designation_name", unique=True),
    )


class Employee(Base, TenantMixin, TimestampMixin):
    """Employee record with certifications, lifecycle states, and organizational hierarchy."""

    __tablename__ = "employees"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_code: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL")
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True
    )
    designation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designations.designation_id"), nullable=True
    )
    reports_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FULL_TIME"  # FULL_TIME, PART_TIME, CONTRACT, INTERN
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"  # ACTIVE, ON_LEAVE, SUSPENDED, LEFT
    )
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emergency_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bank_account_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iban_or_routing: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    __table_args__ = (
        Index("idx_emp_tenant_code", "tenant_id", "employee_code", unique=True),
        Index("idx_emp_dept", "tenant_id", "department_id"),
        Index("idx_emp_status", "tenant_id", "status"),
    )


class EmployeeOnboarding(Base, TenantMixin, TimestampMixin):
    """Employee onboarding checklist container."""

    __tablename__ = "employee_onboardings"

    onboarding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    onboarding_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    job_applicant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    date_of_joining: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"  # PENDING, IN_PROGRESS, COMPLETED
    )

    tasks = relationship("OnboardingTask", back_populates="onboarding", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_onb_tenant_num", "tenant_id", "onboarding_number", unique=True),
    )


class OnboardingTask(Base, TenantMixin, TimestampMixin):
    """Granular actionable task item within an onboarding workflow."""

    __tablename__ = "onboarding_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    onboarding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_onboardings.onboarding_id"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    onboarding = relationship("EmployeeOnboarding", back_populates="tasks")


class EmployeeSeparation(Base, TenantMixin, TimestampMixin):
    """Employee separation / offboarding checklist container."""

    __tablename__ = "employee_separations"

    separation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    separation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    resignation_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_interview_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"  # PENDING, IN_PROGRESS, COMPLETED
    )

    tasks = relationship("SeparationTask", back_populates="separation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sep_tenant_num", "tenant_id", "separation_number", unique=True),
    )


class SeparationTask(Base, TenantMixin, TimestampMixin):
    """Handover task, asset return, or clearance item during employee exit."""

    __tablename__ = "separation_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    separation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_separations.separation_id"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    separation = relationship("EmployeeSeparation", back_populates="tasks")


class ShiftType(Base, TenantMixin, TimestampMixin):
    """Shift definition with timings, grace periods, and late thresholds."""

    __tablename__ = "shift_types"

    shift_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[str] = mapped_column(String(16), nullable=False)  # "09:00:00"
    end_time: Mapped[str] = mapped_column(String(16), nullable=False)    # "17:00:00"
    grace_period_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    half_day_threshold_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("4.00")
    )
    late_mark_after_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_shift_type_name", "tenant_id", "shift_name", unique=True),
    )


class ShiftAssignment(Base, TenantMixin, TimestampMixin):
    """Assignment of shift type to employee for a schedule window."""

    __tablename__ = "shift_assignments"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    shift_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shift_types.shift_type_id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"  # ACTIVE, INACTIVE
    )

    __table_args__ = (
        Index("idx_shift_assign", "tenant_id", "employee_id", "start_date"),
    )


class Attendance(Base, TenantMixin, TimestampMixin):
    """Daily employee attendance log with punch timestamps and compliance flags."""

    __tablename__ = "attendances"

    attendance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PRESENT"  # PRESENT, ABSENT, ON_LEAVE, HALF_DAY
    )
    in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    late_entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    early_exit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    working_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_att_tenant_emp_date", "tenant_id", "employee_id", "attendance_date", unique=True),
        Index("idx_att_date_status", "tenant_id", "attendance_date", "status"),
    )


class LeaveType(Base, TenantMixin, TimestampMixin):
    """Leave policy category definitions."""

    __tablename__ = "leave_types"

    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type_name: Mapped[str] = mapped_column(String(64), nullable=False)  # Casual, Sick, Annual, Maternity, LWP
    max_days_allowed: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    is_carry_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lwp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, doc="Leave Without Pay"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_leave_type_name", "tenant_id", "type_name", unique=True),
    )


class LeaveAllocation(Base, TenantMixin, TimestampMixin):
    """Annual entitlement and quota allocation for an employee."""

    __tablename__ = "leave_allocations"

    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.leave_type_id"), nullable=False
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_leaves_allocated: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carry_forward_leaves: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("0.00")
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index("idx_leave_alloc_emp_type_yr", "tenant_id", "employee_id", "leave_type_id", "fiscal_year", unique=True),
    )


class LeaveApplication(Base, TenantMixin, TimestampMixin):
    """Leave request filed by employee for manager authorization."""

    __tablename__ = "leave_applications"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.leave_type_id"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_leave_days: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, APPROVED, REJECTED, CANCELLED
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )

    __table_args__ = (
        Index("idx_leave_app_num", "tenant_id", "application_number", unique=True),
        Index("idx_leave_app_emp_dates", "tenant_id", "employee_id", "from_date", "to_date"),
    )


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
        default="SCHEDULED",  # SCHEDULED, SWAP_REQUESTED, COMPLETED, CANCELLED, TRANSFERRED
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
        default="SUBMITTED",  # SUBMITTED, AUTO_APPROVED, FLAGGED, APPROVED, PAID, REJECTED
    )
    auto_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    violation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_exp_tenant_number", "tenant_id", "claim_number", unique=True),)
