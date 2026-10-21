"""Deep HR workflows: recruitment, lifecycle, leave, grievance, exit, and work summaries."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class StaffingPlan(Base, TenantMixin, TimestampMixin):
    __tablename__ = "staffing_plans"
    staffing_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    notes: Mapped[str | None] = mapped_column(Text)
    details: Mapped[list["StaffingPlanDetail"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "plan_name", "fiscal_year", name="uq_staffing_plan_tenant_year_name"), CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','CLOSED')", name="ck_staffing_plan_status"))


class StaffingPlanDetail(Base, TenantMixin, TimestampMixin):
    __tablename__ = "staffing_plan_details"
    staffing_plan_detail_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffing_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staffing_plans.staffing_plan_id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.department_id"))
    designation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("designations.designation_id"))
    planned_headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    current_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    justification: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[StaffingPlan] = relationship(back_populates="details")
    __table_args__ = (CheckConstraint("planned_headcount >= 0 AND current_headcount >= 0", name="ck_staffing_plan_headcount"),)


class InterviewRound(Base, TenantMixin, TimestampMixin):
    __tablename__ = "interview_rounds"
    interview_round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "round_name", name="uq_interview_round_tenant_name"), CheckConstraint("sequence_no > 0", name="ck_interview_round_sequence"))


class Interview(Base, TenantMixin, TimestampMixin):
    __tablename__ = "interviews"
    interview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    interview_round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("interview_rounds.interview_round_id"), nullable=False)
    interviewer_employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SCHEDULED")
    outcome: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    meeting_location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(["application_id", "tenant_id"], ["candidate_applications.application_id", "candidate_applications.tenant_id"], ondelete="CASCADE", name="fk_interview_application_tenant"), CheckConstraint("duration_minutes > 0", name="ck_interview_duration"), CheckConstraint("status IN ('SCHEDULED','COMPLETED','CANCELLED')", name="ck_interview_status"), CheckConstraint("outcome IN ('PENDING','SELECTED','REJECTED','ON_HOLD')", name="ck_interview_outcome"), Index("ix_interview_tenant_schedule", "tenant_id", "scheduled_at"))


class InterviewFeedback(Base, TenantMixin, TimestampMixin):
    __tablename__ = "interview_feedback"
    interview_feedback_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("interviews.interview_id", ondelete="CASCADE"), nullable=False)
    interviewer_employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    strengths: Mapped[str | None] = mapped_column(Text)
    concerns: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    __table_args__ = (CheckConstraint("rating >= 0 AND rating <= 5", name="ck_interview_feedback_rating"), CheckConstraint("recommendation IN ('PENDING','YES','NO','HOLD')", name="ck_interview_feedback_recommendation"), UniqueConstraint("tenant_id", "interview_id", "interviewer_employee_id", name="uq_interview_feedback_interviewer"))


class EmployeeGrade(Base, TenantMixin, TimestampMixin):
    __tablename__ = "employee_grades"
    employee_grade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grade_code: Mapped[str] = mapped_column(String(32), nullable=False)
    grade_name: Mapped[str] = mapped_column(String(128), nullable=False)
    minimum_salary: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    maximum_salary: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "grade_code", name="uq_employee_grade_tenant_code"), CheckConstraint("minimum_salary IS NULL OR minimum_salary >= 0", name="ck_employee_grade_min_salary"), CheckConstraint("maximum_salary IS NULL OR maximum_salary >= 0", name="ck_employee_grade_max_salary"), CheckConstraint("minimum_salary IS NULL OR maximum_salary IS NULL OR maximum_salary >= minimum_salary", name="ck_employee_grade_salary_range"))


class EmployeePromotion(Base, TenantMixin, TimestampMixin):
    __tablename__ = "employee_promotions"
    promotion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    from_designation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("designations.designation_id"))
    to_designation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("designations.designation_id"))
    from_grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employee_grades.employee_grade_id"))
    to_grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employee_grades.employee_grade_id"))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    __table_args__ = (CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_employee_promotion_status"), Index("ix_employee_promotion_tenant_employee_date", "tenant_id", "employee_id", "effective_date"))


class EmployeeTransfer(Base, TenantMixin, TimestampMixin):
    __tablename__ = "employee_transfers"
    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    from_department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.department_id"))
    to_department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.department_id"))
    from_reports_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    to_reports_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    __table_args__ = (CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_employee_transfer_status"), Index("ix_employee_transfer_tenant_employee_date", "tenant_id", "employee_id", "effective_date"))


class GrievanceType(Base, TenantMixin, TimestampMixin):
    __tablename__ = "grievance_types"
    grievance_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "type_name", name="uq_grievance_type_tenant_name"),)


class EmployeeGrievance(Base, TenantMixin, TimestampMixin):
    __tablename__ = "employee_grievances"
    grievance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    grievance_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grievance_types.grievance_type_id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="ck_employee_grievance_priority"), CheckConstraint("status IN ('OPEN','UNDER_REVIEW','RESOLVED','CLOSED','REJECTED')", name="ck_employee_grievance_status"), Index("ix_employee_grievance_tenant_status", "tenant_id", "status", "created_at"))


class FullAndFinalStatement(Base, TenantMixin, TimestampMixin):
    __tablename__ = "full_and_final_statements"
    statement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    separation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employee_separations.separation_id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    total_earnings: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    net_payable: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    notes: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list["FullAndFinalStatementItem"]] = relationship(back_populates="statement", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "separation_id", name="uq_full_final_tenant_separation"), CheckConstraint("total_earnings >= 0 AND total_deductions >= 0", name="ck_full_final_totals_nonnegative"), CheckConstraint("status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PAID','CANCELLED')", name="ck_full_final_status"))


class FullAndFinalStatementItem(Base, TenantMixin, TimestampMixin):
    __tablename__ = "full_and_final_statement_items"
    statement_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("full_and_final_statements.statement_id", ondelete="CASCADE"), nullable=False)
    component_type: Mapped[str] = mapped_column(String(24), nullable=False)
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    statement: Mapped[FullAndFinalStatement] = relationship(back_populates="items")
    __table_args__ = (CheckConstraint("component_type IN ('EARNING','DEDUCTION')", name="ck_full_final_item_type"), CheckConstraint("amount >= 0", name="ck_full_final_item_amount"))


class DailyWorkSummary(Base, TenantMixin, TimestampMixin):
    __tablename__ = "daily_work_summaries"
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SUBMITTED")
    replies: Mapped[list["DailyWorkSummaryReply"]] = relationship(back_populates="summary_record", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "employee_id", "work_date", name="uq_daily_work_employee_date"), CheckConstraint("status IN ('DRAFT','SUBMITTED','REVIEWED')", name="ck_daily_work_status"))


class DailyWorkSummaryReply(Base, TenantMixin, TimestampMixin):
    __tablename__ = "daily_work_summary_replies"
    reply_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("daily_work_summaries.summary_id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    summary_record: Mapped[DailyWorkSummary] = relationship(back_populates="replies")


class LeavePolicy(Base, TenantMixin, TimestampMixin):
    __tablename__ = "leave_policies"
    leave_policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    details: Mapped[list["LeavePolicyDetail"]] = relationship(back_populates="policy", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "policy_name", name="uq_leave_policy_tenant_name"),)


class LeavePolicyDetail(Base, TenantMixin, TimestampMixin):
    __tablename__ = "leave_policy_details"
    leave_policy_detail_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leave_policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_policies.leave_policy_id", ondelete="CASCADE"), nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_types.leave_type_id"), nullable=False)
    annual_allocation: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    carry_forward_limit: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    policy: Mapped[LeavePolicy] = relationship(back_populates="details")
    __table_args__ = (UniqueConstraint("tenant_id", "leave_policy_id", "leave_type_id", name="uq_leave_policy_detail_type"), CheckConstraint("annual_allocation >= 0 AND carry_forward_limit >= 0", name="ck_leave_policy_detail_nonnegative"))


class LeavePolicyAssignment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "leave_policy_assignments"
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leave_policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_policies.leave_policy_id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("tenant_id", "employee_id", "fiscal_year", name="uq_leave_policy_assignment_employee_year"),)


class LeaveBlockList(Base, TenantMixin, TimestampMixin):
    __tablename__ = "leave_block_lists"
    leave_block_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_name: Mapped[str] = mapped_column(String(128), nullable=False)
    leave_type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_types.leave_type_id"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.department_id"))
    reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dates: Mapped[list["LeaveBlockListDate"]] = relationship(back_populates="block_list", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "list_name", name="uq_leave_block_list_tenant_name"),)


class LeaveBlockListDate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "leave_block_list_dates"
    leave_block_date_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leave_block_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_block_lists.leave_block_list_id", ondelete="CASCADE"), nullable=False)
    blocked_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    block_list: Mapped[LeaveBlockList] = relationship(back_populates="dates")
    __table_args__ = (UniqueConstraint("tenant_id", "leave_block_list_id", "blocked_date", name="uq_leave_block_date"),)


class CompensatoryLeaveRequest(Base, TenantMixin, TimestampMixin):
    __tablename__ = "compensatory_leave_requests"
    compensatory_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_days: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"))
    __table_args__ = (CheckConstraint("requested_days > 0 AND requested_days <= 2", name="ck_comp_leave_days"), CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_comp_leave_status"), UniqueConstraint("tenant_id", "employee_id", "work_date", name="uq_comp_leave_employee_work_date"))

