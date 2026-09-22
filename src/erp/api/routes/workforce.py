"""Workforce and Human Capital Management API Endpoints (PRD §Shift Scheduling & Expense Management)."""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.hr import Employee, ExpenseClaim
from erp.db.models.operator_cert import OperatorCertificationRecord
from erp.workforce.certifications import OperatorCertification, certification_verifier
from erp.workforce.expense_auditor import (
    ExpenseAuditRequest,
    ExpenseAuditResult,
    expense_auditor,
)
from erp.workforce.shift_swapper import (
    ShiftTradeEvaluationResult,
    ShiftTradeRequest,
    shift_coordinator,
)

router = APIRouter(prefix="/workforce", tags=["Workforce & HR Agent"])


class CreateEmployeeRequest(BaseModel):
    employee_code: str = Field(..., min_length=2, max_length=64)
    first_name: str = Field(..., min_length=1, max_length=64)
    last_name: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    department: str = Field(..., min_length=2, max_length=64)
    certifications: list[str] = Field(default_factory=list)
    max_weekly_hours: int = Field(default=48, ge=20, le=70)


class CreateCertificationRequest(BaseModel):
    employee_code: str = Field(..., min_length=2, max_length=64)
    certification_code: str = Field(..., min_length=2, max_length=64)
    certification_name: str = Field(..., min_length=2, max_length=128)
    issue_date: date
    expiry_date: date


@router.get("/employees", summary="List all employees for tenant")
async def list_employees(
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Returns active and inactive employees for the authenticated tenant."""
    stmt = (
        select(Employee)
        .where(Employee.tenant_id == tenant_id)
        .order_by(Employee.employee_code.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/employees", status_code=status.HTTP_201_CREATED, summary="Create new employee")
async def create_employee(
    req: CreateEmployeeRequest,
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Adds a new workforce employee record."""
    existing = (
        await db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.employee_code == req.employee_code,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Employee with code '{req.employee_code}' already exists.",
        )

    emp = Employee(
        tenant_id=tenant_id,
        employee_code=req.employee_code,
        first_name=req.first_name,
        last_name=req.last_name,
        email=req.email,
        department=req.department,
        certifications=req.certifications,
        max_weekly_hours=req.max_weekly_hours,
        is_active=True,
    )
    db.add(emp)
    await db.flush()
    return emp


@router.get("/certifications", summary="List active operator certifications from DB")
async def list_certifications(
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Returns active safety certification registry for plant operators from PostgreSQL."""
    stmt = (
        select(OperatorCertificationRecord)
        .where(OperatorCertificationRecord.tenant_id == tenant_id)
        .order_by(OperatorCertificationRecord.employee_code.asc())
    )
    records = (await db.execute(stmt)).scalars().all()
    return {
        "certifications": [
            {
                "cert_id": str(r.cert_id),
                "employee_code": r.employee_code,
                "certification_code": r.certification_code,
                "certification_name": r.certification_name,
                "issue_date": r.issue_date.isoformat(),
                "expires_at": r.expiry_date.isoformat(),
                "is_active": r.is_active,
            }
            for r in records
        ]
    }


@router.post("/certifications", status_code=status.HTTP_201_CREATED, summary="Add certification")
async def add_certification(
    req: CreateCertificationRequest,
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Registers a verified safety certification for a plant operator."""
    cert = OperatorCertificationRecord(
        tenant_id=tenant_id,
        employee_code=req.employee_code,
        certification_code=req.certification_code,
        certification_name=req.certification_name,
        issue_date=req.issue_date,
        expiry_date=req.expiry_date,
        is_active=True,
    )
    db.add(cert)

    # Also keep certification_verifier cache synchronized
    if req.employee_code not in certification_verifier._operator_certs:
        certification_verifier._operator_certs[req.employee_code] = []
    certification_verifier._operator_certs[req.employee_code].append(
        OperatorCertification(
            certification_code=req.certification_code,
            certification_name=req.certification_name,
            issue_date=req.issue_date,
            expiry_date=req.expiry_date,
            is_active=True,
        )
    )

    await db.flush()
    return cert


@router.get("/expenses", summary="List employee expense claims")
async def list_expense_claims(
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Returns expense claims for the tenant."""
    stmt = (
        select(ExpenseClaim)
        .where(ExpenseClaim.tenant_id == tenant_id)
        .order_by(ExpenseClaim.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/expense/audit", response_model=ExpenseAuditResult)
async def audit_expense_claim(
    claim: ExpenseAuditRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> ExpenseAuditResult:
    """Audits expense receipts against corporate policy and persists to database."""
    try:
        result = await expense_auditor.audit_and_reimburse(
            session=session,
            tenant_id=tenant_id,
            claim=claim,
        )

        # Look up employee if exists
        emp = (
            await session.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.employee_code == claim.employee_code,
                )
            )
        ).scalar_one_or_none()

        if not emp:
            emp = Employee(
                tenant_id=tenant_id,
                employee_code=claim.employee_code,
                first_name="Operator",
                last_name=claim.employee_code.replace("EMP-", "") or "Staff",
                email=f"{claim.employee_code.lower().replace('_', '-')[:30]}@company.internal",
                department="MANUFACTURING",
                max_weekly_hours=48,
                is_active=True,
            )
            session.add(emp)
            await session.flush()

        emp_id = emp.employee_id
        claim_record = ExpenseClaim(
            tenant_id=tenant_id,
            claim_number=claim.claim_id,
            employee_id=emp_id,
            claim_date=claim.claim_date,
            merchant_name="Corporate Travel Vendor",
            category=claim.expense_category,
            total_amount=claim.total_amount,
            currency="USD",
            receipt_image_hash=claim.receipt_image_hash,
            status="AUTO_APPROVED" if result.is_auto_approved else "FLAGGED",
            auto_approved=result.is_auto_approved,
            violation_notes="; ".join(result.policy_violations)
            if result.policy_violations
            else None,
        )
        session.add(claim_record)
        await session.flush()

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expense audit failed: {e!s}",
        ) from e


from datetime import date, datetime, timedelta

from erp.db.models.hr import Employee, ExpenseClaim, ShiftSchedule


class CreateShiftRequest(BaseModel):
    shift_code: str = Field(..., min_length=2, max_length=64)
    employee_code: str = Field(..., min_length=2, max_length=64)
    shift_date: date
    start_time: datetime
    end_time: datetime
    status: str = "SCHEDULED"


@router.get("/shifts", summary="List scheduled shifts")
async def list_shifts(
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Returns scheduled shifts from PostgreSQL."""
    stmt = (
        select(ShiftSchedule, Employee.employee_code, Employee.first_name, Employee.last_name)
        .join(Employee, ShiftSchedule.employee_id == Employee.employee_id)
        .where(ShiftSchedule.tenant_id == tenant_id)
        .order_by(ShiftSchedule.shift_date.desc(), ShiftSchedule.start_time.asc())
    )
    rows = (await db.execute(stmt)).all()
    shifts = []
    for s, emp_code, fn, ln in rows:
        shifts.append({
            "shift_id": str(s.shift_id),
            "shift_code": s.shift_code,
            "employee_code": emp_code,
            "employee_name": f"{fn} {ln}",
            "shift_date": s.shift_date.isoformat(),
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat(),
            "status": s.status,
        })
    return shifts


@router.post("/shifts", status_code=status.HTTP_201_CREATED, summary="Create shift")
async def create_shift(
    req: CreateShiftRequest,
    db: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Creates a new scheduled shift for an employee."""
    emp = (
        await db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.employee_code == req.employee_code,
            )
        )
    ).scalar_one_or_none()

    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee '{req.employee_code}' not found.",
        )

    shift = ShiftSchedule(
        tenant_id=tenant_id,
        shift_code=req.shift_code,
        employee_id=emp.employee_id,
        shift_date=req.shift_date,
        start_time=req.start_time,
        end_time=req.end_time,
        status=req.status,
    )
    db.add(shift)
    await db.flush()
    return {
        "shift_id": str(shift.shift_id),
        "shift_code": shift.shift_code,
        "employee_code": req.employee_code,
        "shift_date": shift.shift_date.isoformat(),
        "start_time": shift.start_time.isoformat(),
        "end_time": shift.end_time.isoformat(),
        "status": shift.status,
    }


@router.post("/shift-trade/evaluate", response_model=ShiftTradeEvaluationResult)
async def evaluate_shift_trade(
    request: ShiftTradeRequest,
    db: DbSessionDep,
    tenant_id: TenantIdDep,
) -> ShiftTradeEvaluationResult:
    """Evaluates peer shift trade request verifying DB roster invariants and persists reassignment if compliant."""
    try:
        target_emp = (
            await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.employee_code == request.target_employee,
                )
            )
        ).scalar_one_or_none()

        req_emp = (
            await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.employee_code == request.requesting_employee,
                )
            )
        ).scalar_one_or_none()

        # If shift_id or shift_code specified, load shift
        matched_shift = None
        if request.shift_id:
            matched_shift = (
                await db.execute(
                    select(ShiftSchedule).where(
                        ShiftSchedule.tenant_id == tenant_id,
                        ShiftSchedule.shift_id == request.shift_id,
                    )
                )
            ).scalar_one_or_none()
        elif request.shift_code:
            matched_shift = (
                await db.execute(
                    select(ShiftSchedule).where(
                        ShiftSchedule.tenant_id == tenant_id,
                        ShiftSchedule.shift_code == request.shift_code,
                    )
                )
            ).scalar_one_or_none()

        if matched_shift and request.target_proposed_shift_start is None:
            request.target_proposed_shift_start = matched_shift.start_time
            request.shift_duration_hours = (
                matched_shift.end_time - matched_shift.start_time
            ).total_seconds() / 3600.0

        ref_date = (
            request.target_proposed_shift_start.date()
            if request.target_proposed_shift_start
            else date.today()
        )

        # Look up target employee's scheduled hours from DB in 7-day window if available
        if target_emp and request.target_current_weekly_hours is None:
            week_start = ref_date - timedelta(days=ref_date.weekday())
            week_end = week_start + timedelta(days=6)
            db_shifts = (
                await db.execute(
                    select(ShiftSchedule).where(
                        ShiftSchedule.tenant_id == tenant_id,
                        ShiftSchedule.employee_id == target_emp.employee_id,
                        ShiftSchedule.shift_date >= week_start,
                        ShiftSchedule.shift_date <= week_end,
                    )
                )
            ).scalars().all()
            total_hours = sum(
                (s.end_time - s.start_time).total_seconds() / 3600.0 for s in db_shifts
            )
            request.target_current_weekly_hours = total_hours

            # Look up previous shift end time
            if request.target_previous_shift_end is None and request.target_proposed_shift_start:
                prev_shift = (
                    await db.execute(
                        select(ShiftSchedule)
                        .where(
                            ShiftSchedule.tenant_id == tenant_id,
                            ShiftSchedule.employee_id == target_emp.employee_id,
                            ShiftSchedule.end_time <= request.target_proposed_shift_start,
                        )
                        .order_by(ShiftSchedule.end_time.desc())
                    )
                ).scalars().first()
                if prev_shift:
                    request.target_previous_shift_end = prev_shift.end_time

        result = shift_coordinator.evaluate_and_execute_trade(request)

        # If approved and target employee found, persist transfer to database
        if result.is_approved and target_emp:
            if matched_shift:
                matched_shift.employee_id = target_emp.employee_id
                matched_shift.status = "TRANSFERRED"
            elif req_emp:
                # Find requesting employee's shift on trade date
                req_shift = (
                    await db.execute(
                        select(ShiftSchedule).where(
                            ShiftSchedule.tenant_id == tenant_id,
                            ShiftSchedule.employee_id == req_emp.employee_id,
                            ShiftSchedule.shift_date == ref_date,
                        )
                    )
                ).scalars().first()
                if req_shift:
                    req_shift.employee_id = target_emp.employee_id
                    req_shift.status = "TRANSFERRED"
                elif request.target_proposed_shift_start:
                    new_shift = ShiftSchedule(
                        tenant_id=tenant_id,
                        shift_code=f"SHIFT-TRD-{request.trade_id[:6].upper()}",
                        employee_id=target_emp.employee_id,
                        shift_date=ref_date,
                        start_time=request.target_proposed_shift_start,
                        end_time=request.target_proposed_shift_start
                        + timedelta(hours=request.shift_duration_hours),
                        status="TRANSFERRED",
                    )
                    db.add(new_shift)
            await db.flush()

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shift trade evaluation failed: {e!s}",
        ) from e

