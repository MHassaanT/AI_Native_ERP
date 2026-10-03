"""Human Resources & Employee Lifecycle API Routes."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.hr import (
    attendance_service,
    employee_service,
    expense_advance_service,
    leave_service,
)

router = APIRouter(prefix="/hr", tags=["HR & Workforce Lifecycle"])


# --- Schemas ---

class CreateDepartmentRequest(BaseModel):
    department_name: str = Field(..., min_length=2, max_length=128)
    parent_department_id: uuid.UUID | None = None
    department_head_id: uuid.UUID | None = None


class CreateDesignationRequest(BaseModel):
    designation_name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None


class CreateEmployeeFullRequest(BaseModel):
    employee_code: str = Field(..., min_length=2, max_length=64)
    first_name: str = Field(..., min_length=1, max_length=64)
    last_name: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    department_name: str = "GENERAL"
    department_id: uuid.UUID | None = None
    designation_name: str | None = None
    designation_id: uuid.UUID | None = None
    reports_to_id: uuid.UUID | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    date_of_joining: date | None = None
    employment_type: str = "FULL_TIME"
    phone: str | None = None
    emergency_phone: str | None = None
    bank_name: str | None = None
    bank_account_no: str | None = None
    iban_or_routing: str | None = None
    certifications: list[str] = Field(default_factory=list)
    max_weekly_hours: int = 48


class CreateOnboardingRequest(BaseModel):
    employee_id: uuid.UUID
    job_applicant_name: str | None = None
    date_of_joining: date | None = None
    task_names: list[str] | None = None


class CreateSeparationRequest(BaseModel):
    employee_id: uuid.UUID
    resignation_date: date
    exit_interview_notes: str | None = None
    task_names: list[str] | None = None


class CreateShiftTypeRequest(BaseModel):
    shift_name: str = Field(..., min_length=2, max_length=64)
    start_time: str = "09:00:00"
    end_time: str = "17:00:00"
    grace_period_mins: int = 15
    half_day_threshold_hours: Decimal = Decimal("4.00")
    late_mark_after_mins: int = 15


class CreateShiftAssignmentRequest(BaseModel):
    employee_id: uuid.UUID
    shift_type_id: uuid.UUID
    start_date: date
    end_date: date | None = None


class MarkAttendanceRequest(BaseModel):
    employee_id: uuid.UUID
    attendance_date: date
    status: str = "PRESENT"
    in_time: datetime | None = None
    out_time: datetime | None = None
    remarks: str | None = None


class CreateLeaveTypeRequest(BaseModel):
    type_name: str = Field(..., min_length=2, max_length=64)
    max_days_allowed: int = 14
    is_carry_forward: bool = False
    is_lwp: bool = False


class AllocateLeaveRequest(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    fiscal_year: int
    total_leaves_allocated: Decimal
    carry_forward_leaves: Decimal = Decimal("0.00")
    from_date: date | None = None
    to_date: date | None = None


class SubmitLeaveApplicationRequest(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    from_date: date
    to_date: date
    total_leave_days: Decimal
    is_half_day: bool = False
    reason: str = "Personal Leave"


class CreateAdvanceRequest(BaseModel):
    employee_id: uuid.UUID
    advance_amount: Decimal = Field(..., gt=0)
    purpose: str = Field(..., min_length=2)
    monthly_deduction_amount: Decimal = Field(..., gt=0)
    posting_date: date | None = None


# --- Endpoints ---

# Departments
@router.post("/departments", status_code=status.HTTP_201_CREATED, summary="Create department")
async def create_department(req: CreateDepartmentRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.create_department(
        db, tenant_id, req.department_name, req.parent_department_id, req.department_head_id
    )


@router.get("/departments", summary="List departments")
async def list_departments(tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.list_departments(db, tenant_id)


# Designations
@router.post("/designations", status_code=status.HTTP_201_CREATED, summary="Create designation")
async def create_designation(req: CreateDesignationRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.create_designation(db, tenant_id, req.designation_name, req.description)


@router.get("/designations", summary="List designations")
async def list_designations(tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.list_designations(db, tenant_id)


# Employees
@router.post("/employees", status_code=status.HTTP_201_CREATED, summary="Create employee with full HR attributes")
async def create_employee_full(req: CreateEmployeeFullRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await employee_service.create_employee(
            db=db,
            tenant_id=tenant_id,
            employee_code=req.employee_code,
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            department_name=req.department_name,
            department_id=req.department_id,
            designation_name=req.designation_name,
            designation_id=req.designation_id,
            reports_to_id=req.reports_to_id,
            gender=req.gender,
            date_of_birth=req.date_of_birth,
            date_of_joining=req.date_of_joining,
            employment_type=req.employment_type,
            phone=req.phone,
            emergency_phone=req.emergency_phone,
            bank_name=req.bank_name,
            bank_account_no=req.bank_account_no,
            iban_or_routing=req.iban_or_routing,
            certifications=req.certifications,
            max_weekly_hours=req.max_weekly_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create employee: {str(e)}") from e


@router.get("/employees", summary="List employees")
async def list_employees_hr(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    department_id: uuid.UUID | None = None,
    status: str | None = None,
):
    return await employee_service.list_employees(db, tenant_id, department_id, status)


@router.get("/employees/{employee_id}", summary="Get employee details")
async def get_employee_hr(employee_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    emp = await employee_service.get_employee(db, tenant_id, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


# Onboarding & Separation
@router.post("/onboarding", status_code=status.HTTP_201_CREATED, summary="Start employee onboarding")
async def start_onboarding(req: CreateOnboardingRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.create_onboarding(
        db, tenant_id, req.employee_id, req.job_applicant_name, req.date_of_joining, req.task_names
    )


@router.get("/onboarding", summary="List onboarding checklists")
async def list_onboardings(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
):
    return await employee_service.list_onboardings(db, tenant_id, employee_id)


@router.post("/onboarding/{onboarding_id}/tasks/{task_id}/complete", summary="Complete onboarding task")
async def complete_onb_task(onboarding_id: uuid.UUID, task_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await employee_service.complete_onboarding_task(db, tenant_id, onboarding_id, task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/separation", status_code=status.HTTP_201_CREATED, summary="Start employee separation")
async def start_separation(req: CreateSeparationRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await employee_service.create_separation(
        db, tenant_id, req.employee_id, req.resignation_date, req.exit_interview_notes, req.task_names
    )


@router.get("/separation", summary="List separation exit records")
async def list_separations(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
):
    return await employee_service.list_separations(db, tenant_id, employee_id)


@router.post("/separation/{separation_id}/tasks/{task_id}/complete", summary="Complete separation task")
async def complete_sep_task(separation_id: uuid.UUID, task_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await employee_service.complete_separation_task(db, tenant_id, separation_id, task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Shifts & Attendance
@router.post("/shifts/types", status_code=status.HTTP_201_CREATED, summary="Create shift type")
async def create_shift_type(req: CreateShiftTypeRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await attendance_service.create_shift_type(
        db, tenant_id, req.shift_name, req.start_time, req.end_time,
        req.grace_period_mins, req.half_day_threshold_hours, req.late_mark_after_mins
    )


@router.get("/shifts/types", summary="List shift types")
async def list_shift_types(tenant_id: TenantIdDep, db: DbSessionDep):
    return await attendance_service.list_shift_types(db, tenant_id)


@router.post("/shifts/assignments", status_code=status.HTTP_201_CREATED, summary="Assign shift to employee")
async def assign_shift(req: CreateShiftAssignmentRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await attendance_service.assign_shift(
        db, tenant_id, req.employee_id, req.shift_type_id, req.start_date, req.end_date
    )


@router.post("/attendance/punch", summary="Mark daily attendance punch")
async def mark_attendance(req: MarkAttendanceRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await attendance_service.mark_attendance(
        db, tenant_id, req.employee_id, req.attendance_date, req.status, req.in_time, req.out_time, req.remarks
    )


@router.get("/attendance", summary="List attendance logs")
async def list_attendance(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    return await attendance_service.list_attendances(db, tenant_id, employee_id, from_date, to_date)


# Leaves
@router.post("/leaves/types", status_code=status.HTTP_201_CREATED, summary="Create leave type")
async def create_leave_type(req: CreateLeaveTypeRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await leave_service.create_leave_type(
            db, tenant_id, req.type_name, req.max_days_allowed, req.is_carry_forward, req.is_lwp
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/leaves/types", summary="List leave types")
async def list_leave_types(tenant_id: TenantIdDep, db: DbSessionDep):
    return await leave_service.list_leave_types(db, tenant_id)


@router.post("/leaves/allocations", status_code=status.HTTP_201_CREATED, summary="Allocate annual leaves")
async def allocate_leaves(req: AllocateLeaveRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await leave_service.allocate_leaves(
        db, tenant_id, req.employee_id, req.leave_type_id, req.fiscal_year,
        req.total_leaves_allocated, req.carry_forward_leaves, req.from_date, req.to_date
    )


@router.get("/leaves/balance", summary="Query employee leave balance")
async def get_leave_balance(
    employee_id: uuid.UUID,
    leave_type_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    fiscal_year: int | None = None,
):
    try:
        return await leave_service.get_leave_balance(db, tenant_id, employee_id, leave_type_id, fiscal_year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/leaves/applications", status_code=status.HTTP_201_CREATED, summary="Submit leave application")
async def submit_leave_application(req: SubmitLeaveApplicationRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await leave_service.submit_leave_application(
            db, tenant_id, req.employee_id, req.leave_type_id, req.from_date, req.to_date,
            req.total_leave_days, req.is_half_day, req.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/leaves/applications", summary="List leave applications")
async def list_leave_applications(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
):
    return await leave_service.list_leave_applications(db, tenant_id, employee_id, status)


@router.post("/leaves/applications/{application_id}/approve", summary="Approve leave application")
async def approve_leave(application_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await leave_service.approve_leave_application(db, tenant_id, application_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/leaves/applications/{application_id}/reject", summary="Reject leave application")
async def reject_leave(
    application_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reason: str | None = None,
):
    try:
        return await leave_service.reject_leave_application(db, tenant_id, application_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Advances & Expenses
@router.post("/advances", status_code=status.HTTP_201_CREATED, summary="Create employee advance")
async def create_advance(req: CreateAdvanceRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await expense_advance_service.create_employee_advance(
        db, tenant_id, req.employee_id, req.advance_amount, req.purpose, req.monthly_deduction_amount, req.posting_date
    )


@router.get("/advances", summary="List employee advances")
async def list_advances(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
):
    return await expense_advance_service.list_employee_advances(db, tenant_id, employee_id, status)


@router.post("/advances/{advance_id}/disburse", summary="Approve and disburse advance with GL posting")
async def disburse_advance(advance_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await expense_advance_service.approve_and_disburse_advance(db, tenant_id, advance_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/expenses/{claim_id}/reimburse", summary="Reimburse approved expense claim with GL posting")
async def reimburse_expense(claim_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await expense_advance_service.reimburse_expense_claim(db, tenant_id, claim_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
