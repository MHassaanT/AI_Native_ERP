"""Add Phase C HR deep workflows and reports.

Revision ID: 034_hr_deep_workflows
Revises: 033_buying_selling_enhancements
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "034_hr_deep_workflows"
down_revision: str | None = "033_buying_selling_enhancements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None
U = postgresql.UUID(as_uuid=True)


def common():
    return [
        sa.Column("tenant_id", U, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
    ]


def table(name, pk, *columns, constraints=()):
    op.create_table(name, sa.Column(pk, U, primary_key=True, nullable=False), *common(), *columns, *constraints)


def upgrade() -> None:
    op.add_column("employees", sa.Column("employee_grade_id", U, nullable=True))
    op.create_table(
        "employee_grades", sa.Column("employee_grade_id", U, primary_key=True), *common(),
        sa.Column("grade_code", sa.String(32), nullable=False), sa.Column("grade_name", sa.String(128), nullable=False),
        sa.Column("minimum_salary", sa.Numeric(18, 4)), sa.Column("maximum_salary", sa.Numeric(18, 4)),
        sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tenant_id", "grade_code", name="uq_employee_grade_tenant_code"),
        sa.CheckConstraint("minimum_salary IS NULL OR minimum_salary >= 0", name="ck_employee_grade_min_salary"),
        sa.CheckConstraint("maximum_salary IS NULL OR maximum_salary >= 0", name="ck_employee_grade_max_salary"),
        sa.CheckConstraint("minimum_salary IS NULL OR maximum_salary IS NULL OR maximum_salary >= minimum_salary", name="ck_employee_grade_salary_range"),
    )
    op.create_foreign_key("fk_employee_grade", "employees", "employee_grades", ["employee_grade_id"], ["employee_grade_id"], ondelete="SET NULL")

    table("staffing_plans", "staffing_plan_id", sa.Column("plan_name", sa.String(128), nullable=False), sa.Column("fiscal_year", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("notes", sa.Text()), constraints=(sa.UniqueConstraint("tenant_id", "plan_name", "fiscal_year", name="uq_staffing_plan_tenant_year_name"), sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','CLOSED')", name="ck_staffing_plan_status")))
    table("staffing_plan_details", "staffing_plan_detail_id", sa.Column("staffing_plan_id", U, sa.ForeignKey("staffing_plans.staffing_plan_id", ondelete="CASCADE"), nullable=False), sa.Column("department_id", U, sa.ForeignKey("departments.department_id")), sa.Column("designation_id", U, sa.ForeignKey("designations.designation_id")), sa.Column("planned_headcount", sa.Integer(), nullable=False), sa.Column("current_headcount", sa.Integer(), nullable=False), sa.Column("justification", sa.Text()), constraints=(sa.CheckConstraint("planned_headcount >= 0 AND current_headcount >= 0", name="ck_staffing_plan_headcount"),))
    table("interview_rounds", "interview_round_id", sa.Column("round_name", sa.String(128), nullable=False), sa.Column("sequence_no", sa.Integer(), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "round_name", name="uq_interview_round_tenant_name"), sa.CheckConstraint("sequence_no > 0", name="ck_interview_round_sequence")))
    table("interviews", "interview_id", sa.Column("application_id", U, nullable=False), sa.Column("interview_round_id", U, sa.ForeignKey("interview_rounds.interview_round_id"), nullable=False), sa.Column("interviewer_employee_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False), sa.Column("duration_minutes", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("outcome", sa.String(24), nullable=False), sa.Column("meeting_location", sa.String(255)), sa.Column("notes", sa.Text()), constraints=(sa.ForeignKeyConstraint(["application_id", "tenant_id"], ["candidate_applications.application_id", "candidate_applications.tenant_id"], ondelete="CASCADE", name="fk_interview_application_tenant"), sa.CheckConstraint("duration_minutes > 0", name="ck_interview_duration"), sa.CheckConstraint("status IN ('SCHEDULED','COMPLETED','CANCELLED')", name="ck_interview_status"), sa.CheckConstraint("outcome IN ('PENDING','SELECTED','REJECTED','ON_HOLD')", name="ck_interview_outcome")))
    table("interview_feedback", "interview_feedback_id", sa.Column("interview_id", U, sa.ForeignKey("interviews.interview_id", ondelete="CASCADE"), nullable=False), sa.Column("interviewer_employee_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("rating", sa.Numeric(4, 2), nullable=False), sa.Column("strengths", sa.Text()), sa.Column("concerns", sa.Text()), sa.Column("recommendation", sa.String(24), nullable=False), constraints=(sa.CheckConstraint("rating >= 0 AND rating <= 5", name="ck_interview_feedback_rating"), sa.CheckConstraint("recommendation IN ('PENDING','YES','NO','HOLD')", name="ck_interview_feedback_recommendation"), sa.UniqueConstraint("tenant_id", "interview_id", "interviewer_employee_id", name="uq_interview_feedback_interviewer")))
    table("employee_promotions", "promotion_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("from_designation_id", U, sa.ForeignKey("designations.designation_id")), sa.Column("to_designation_id", U, sa.ForeignKey("designations.designation_id")), sa.Column("from_grade_id", U, sa.ForeignKey("employee_grades.employee_grade_id")), sa.Column("to_grade_id", U, sa.ForeignKey("employee_grades.employee_grade_id")), sa.Column("effective_date", sa.Date(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("approved_by_id", U, sa.ForeignKey("employees.employee_id")), constraints=(sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_employee_promotion_status"),))
    table("employee_transfers", "transfer_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("from_department_id", U, sa.ForeignKey("departments.department_id")), sa.Column("to_department_id", U, sa.ForeignKey("departments.department_id")), sa.Column("from_reports_to_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("to_reports_to_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("effective_date", sa.Date(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("approved_by_id", U, sa.ForeignKey("employees.employee_id")), constraints=(sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_employee_transfer_status"),))
    table("grievance_types", "grievance_type_id", sa.Column("type_name", sa.String(128), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "type_name", name="uq_grievance_type_tenant_name"),))
    table("employee_grievances", "grievance_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("grievance_type_id", U, sa.ForeignKey("grievance_types.grievance_type_id"), nullable=False), sa.Column("subject", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("priority", sa.String(16), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("assigned_to_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("resolution", sa.Text()), sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("is_confidential", sa.Boolean(), nullable=False), constraints=(sa.CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="ck_employee_grievance_priority"), sa.CheckConstraint("status IN ('OPEN','UNDER_REVIEW','RESOLVED','CLOSED','REJECTED')", name="ck_employee_grievance_status"),))
    table("full_and_final_statements", "statement_id", sa.Column("separation_id", U, sa.ForeignKey("employee_separations.separation_id"), nullable=False), sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("settlement_date", sa.Date(), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("total_earnings", sa.Numeric(18, 4), nullable=False), sa.Column("total_deductions", sa.Numeric(18, 4), nullable=False), sa.Column("net_payable", sa.Numeric(18, 4), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("notes", sa.Text()), constraints=(sa.UniqueConstraint("tenant_id", "separation_id", name="uq_full_final_tenant_separation"), sa.CheckConstraint("total_earnings >= 0 AND total_deductions >= 0", name="ck_full_final_totals_nonnegative"), sa.CheckConstraint("status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PAID','CANCELLED')", name="ck_full_final_status")))
    table("full_and_final_statement_items", "statement_item_id", sa.Column("statement_id", U, sa.ForeignKey("full_and_final_statements.statement_id", ondelete="CASCADE"), nullable=False), sa.Column("component_type", sa.String(24), nullable=False), sa.Column("component_code", sa.String(64), nullable=False), sa.Column("description", sa.String(255), nullable=False), sa.Column("amount", sa.Numeric(18, 4), nullable=False), constraints=(sa.CheckConstraint("component_type IN ('EARNING','DEDUCTION')", name="ck_full_final_item_type"), sa.CheckConstraint("amount >= 0", name="ck_full_final_item_amount")))
    table("daily_work_summaries", "summary_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("work_date", sa.Date(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "employee_id", "work_date", name="uq_daily_work_employee_date"), sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','REVIEWED')", name="ck_daily_work_status")))
    table("daily_work_summary_replies", "reply_id", sa.Column("summary_id", U, sa.ForeignKey("daily_work_summaries.summary_id", ondelete="CASCADE"), nullable=False), sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("message", sa.Text(), nullable=False))
    table("leave_policies", "leave_policy_id", sa.Column("policy_name", sa.String(128), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "policy_name", name="uq_leave_policy_tenant_name"),))
    table("leave_policy_details", "leave_policy_detail_id", sa.Column("leave_policy_id", U, sa.ForeignKey("leave_policies.leave_policy_id", ondelete="CASCADE"), nullable=False), sa.Column("leave_type_id", U, sa.ForeignKey("leave_types.leave_type_id"), nullable=False), sa.Column("annual_allocation", sa.Numeric(8, 2), nullable=False), sa.Column("carry_forward_limit", sa.Numeric(8, 2), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "leave_policy_id", "leave_type_id", name="uq_leave_policy_detail_type"), sa.CheckConstraint("annual_allocation >= 0 AND carry_forward_limit >= 0", name="ck_leave_policy_detail_nonnegative")))
    table("leave_policy_assignments", "assignment_id", sa.Column("leave_policy_id", U, sa.ForeignKey("leave_policies.leave_policy_id"), nullable=False), sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("fiscal_year", sa.Integer(), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "employee_id", "fiscal_year", name="uq_leave_policy_assignment_employee_year"),))
    table("leave_block_lists", "leave_block_list_id", sa.Column("list_name", sa.String(128), nullable=False), sa.Column("leave_type_id", U, sa.ForeignKey("leave_types.leave_type_id")), sa.Column("department_id", U, sa.ForeignKey("departments.department_id")), sa.Column("reason", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(sa.UniqueConstraint("tenant_id", "list_name", name="uq_leave_block_list_tenant_name"),))
    table("leave_block_list_dates", "leave_block_date_id", sa.Column("leave_block_list_id", U, sa.ForeignKey("leave_block_lists.leave_block_list_id", ondelete="CASCADE"), nullable=False), sa.Column("blocked_date", sa.Date(), nullable=False), sa.Column("reason", sa.Text()), constraints=(sa.UniqueConstraint("tenant_id", "leave_block_list_id", "blocked_date", name="uq_leave_block_date"),))
    table("compensatory_leave_requests", "compensatory_request_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("work_date", sa.Date(), nullable=False), sa.Column("requested_days", sa.Numeric(5, 2), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("approved_by_id", U, sa.ForeignKey("employees.employee_id")), constraints=(sa.CheckConstraint("requested_days > 0 AND requested_days <= 2", name="ck_comp_leave_days"), sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_comp_leave_status"), sa.UniqueConstraint("tenant_id", "employee_id", "work_date", name="uq_comp_leave_employee_work_date")))

    for name in ("staffing_plans", "staffing_plan_details", "interview_rounds", "interviews", "interview_feedback", "employee_grades", "employee_promotions", "employee_transfers", "grievance_types", "employee_grievances", "full_and_final_statements", "full_and_final_statement_items", "daily_work_summaries", "daily_work_summary_replies", "leave_policies", "leave_policy_details", "leave_policy_assignments", "leave_block_lists", "leave_block_list_dates", "compensatory_leave_requests"):
        op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
    op.create_index("ix_interview_tenant_schedule", "interviews", ["tenant_id", "scheduled_at"])
    op.create_index("ix_employee_promotion_tenant_employee_date", "employee_promotions", ["tenant_id", "employee_id", "effective_date"])
    op.create_index("ix_employee_transfer_tenant_employee_date", "employee_transfers", ["tenant_id", "employee_id", "effective_date"])
    op.create_index("ix_employee_grievance_tenant_status", "employee_grievances", ["tenant_id", "status", "created_at"])
    op.create_index("ix_employees_employee_grade_id", "employees", ["employee_grade_id"])


def downgrade() -> None:
    op.drop_index("ix_employees_employee_grade_id", table_name="employees")
    for name in ("compensatory_leave_requests", "leave_block_list_dates", "leave_block_lists", "leave_policy_assignments", "leave_policy_details", "leave_policies", "daily_work_summary_replies", "daily_work_summaries", "full_and_final_statement_items", "full_and_final_statements", "employee_grievances", "grievance_types", "employee_transfers", "employee_promotions", "interview_feedback", "interviews", "interview_rounds", "staffing_plan_details", "staffing_plans"):
        op.drop_table(name)
    op.drop_constraint("fk_employee_grade", "employees", type_="foreignkey")
    op.drop_column("employees", "employee_grade_id")
    op.drop_table("employee_grades")
