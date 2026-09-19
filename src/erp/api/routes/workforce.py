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

        emp_id = emp.employee_id if emp else uuid.uuid4()
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


@router.post("/shift-trade/evaluate", response_model=ShiftTradeEvaluationResult)
async def evaluate_shift_trade(request: ShiftTradeRequest) -> ShiftTradeEvaluationResult:
    """Evaluates peer shift trade request ensuring >=11h rest, <=48h weekly limit, and safety certs."""
    try:
        return shift_coordinator.evaluate_and_execute_trade(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shift trade evaluation failed: {e!s}",
        ) from e
