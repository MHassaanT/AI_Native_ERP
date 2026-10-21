"""Payroll & Compensation Management API Routes."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.payroll import AdditionalSalary, IncomeTaxSlab, IncomeTaxSlabRate, PayrollPeriod, RetentionBonus
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from erp.workflows.payroll import batch_payroll_service, payroll_service

router = APIRouter(prefix="/payroll", tags=["Payroll & Compensation"])


# --- Schemas ---

class CreateComponentRequest(BaseModel):
    component_name: str = Field(..., min_length=2, max_length=128)
    component_code: str = Field(..., min_length=2, max_length=64)
    component_type: str = Field(..., pattern="^(EARNING|DEDUCTION)$")
    calculation_type: str = "FIXED"  # FIXED, FORMULA
    formula_expression: str | None = None
    is_taxable: bool = True
    account_code: str = "6100-SALARY-EXPENSE"


class StructureItemPayload(BaseModel):
    component_id: uuid.UUID
    amount: Decimal = Decimal("0.0000")
    formula_expression: str | None = None


class CreateStructureRequest(BaseModel):
    structure_name: str = Field(..., min_length=2, max_length=128)
    items: list[StructureItemPayload]
    payroll_frequency: str = "MONTHLY"
    currency: str = "USD"


class AssignStructureRequest(BaseModel):
    employee_id: uuid.UUID
    structure_id: uuid.UUID
    from_date: date
    base_salary: Decimal = Field(..., gt=0)


class GenerateSlipRequest(BaseModel):
    employee_id: uuid.UUID
    posting_date: date
    start_date: date
    end_date: date


class CreateBatchPayrollRequest(BaseModel):
    posting_date: date
    start_date: date
    end_date: date
    department_id: uuid.UUID | None = None


class TaxRatePayload(BaseModel):
    lower_bound: Decimal = Field(..., ge=0)
    upper_bound: Decimal | None = Field(None, gt=0)
    tax_rate: Decimal = Field(..., ge=0, le=1)
    fixed_amount: Decimal = Field(Decimal("0"), ge=0)


class CreateTaxSlabRequest(BaseModel):
    slab_name: str = Field(..., min_length=2, max_length=128)
    tax_year: str = Field(..., min_length=4, max_length=16)
    currency: str = Field("USD", min_length=3, max_length=3)
    effective_from: date
    effective_to: date
    rates: list[TaxRatePayload] = Field(..., min_length=1)


class CreatePayrollPeriodRequest(BaseModel):
    period_name: str = Field(..., min_length=2, max_length=128)
    start_date: date
    end_date: date


class CreateAdditionalSalaryRequest(BaseModel):
    employee_id: uuid.UUID
    salary_component_id: uuid.UUID | None = None
    payroll_date: date
    amount: Decimal = Field(..., gt=0)
    component_name: str = Field(..., min_length=2, max_length=128)
    component_type: str = Field("EARNING", pattern="^(EARNING|DEDUCTION)$")
    is_taxable: bool = True


class CreateRetentionBonusRequest(BaseModel):
    employee_id: uuid.UUID
    bonus_name: str = Field(..., min_length=2, max_length=128)
    amount: Decimal = Field(..., gt=0)
    vesting_date: date
    is_taxable: bool = True


# --- Endpoints ---

# Components
@router.post("/tax-slabs", status_code=status.HTTP_201_CREATED, summary="Create progressive income tax slab")
async def create_tax_slab(req: CreateTaxSlabRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    if req.effective_to < req.effective_from:
        raise HTTPException(status_code=400, detail="Tax slab end date must be on or after its start date.")
    rates = sorted(req.rates, key=lambda rate: rate.lower_bound)
    for index, rate in enumerate(rates):
        if rate.upper_bound is not None and rate.upper_bound <= rate.lower_bound:
            raise HTTPException(status_code=400, detail="Each upper bound must exceed its lower bound.")
        if index and (rates[index - 1].upper_bound is None or rates[index - 1].upper_bound != rate.lower_bound):
            raise HTTPException(status_code=400, detail="Tax bands must be contiguous and non-overlapping.")
    if rates[0].lower_bound != 0 or rates[-1].upper_bound is not None:
        raise HTTPException(status_code=400, detail="Tax bands must start at zero and end with an uncapped band.")
    slab = IncomeTaxSlab(tenant_id=tenant_id, slab_name=req.slab_name, tax_year=req.tax_year,
                         currency=req.currency.upper(), effective_from=req.effective_from,
                         effective_to=req.effective_to, is_active=True)
    db.add(slab)
    await db.flush()
    for rate in rates:
        db.add(IncomeTaxSlabRate(tenant_id=tenant_id, slab_id=slab.slab_id, **rate.model_dump()))
    await db.flush()
    return {"slab_id": slab.slab_id, "slab_name": slab.slab_name, "tax_year": slab.tax_year, "rates": len(rates)}


@router.get("/tax-slabs")
async def list_tax_slabs(tenant_id: TenantIdDep, db: DbSessionDep):
    rows = (await db.execute(select(IncomeTaxSlab).options(selectinload(IncomeTaxSlab.rates)).where(IncomeTaxSlab.tenant_id == tenant_id).order_by(IncomeTaxSlab.effective_from.desc()))).scalars().all()
    return [{"slab_id": s.slab_id, "slab_name": s.slab_name, "tax_year": s.tax_year, "currency": s.currency,
             "effective_from": s.effective_from, "effective_to": s.effective_to, "is_active": s.is_active,
             "rates": [{"lower_bound": r.lower_bound, "upper_bound": r.upper_bound, "tax_rate": r.tax_rate, "fixed_amount": r.fixed_amount} for r in s.rates]} for s in rows]


@router.post("/periods", status_code=status.HTTP_201_CREATED)
async def create_payroll_period(req: CreatePayrollPeriodRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    if req.end_date < req.start_date:
        raise HTTPException(status_code=400, detail="Payroll period end must be on or after start.")
    overlap = (await db.execute(select(PayrollPeriod).where(
        PayrollPeriod.tenant_id == tenant_id, PayrollPeriod.status == "OPEN",
        PayrollPeriod.start_date <= req.end_date, PayrollPeriod.end_date >= req.start_date,
    ))).scalars().first()
    if overlap:
        raise HTTPException(status_code=409, detail=f"Payroll period overlaps open period '{overlap.period_name}'.")
    period = PayrollPeriod(tenant_id=tenant_id, **req.model_dump(), status="OPEN")
    db.add(period)
    await db.flush()
    return period


@router.get("/periods")
async def list_payroll_periods(tenant_id: TenantIdDep, db: DbSessionDep):
    return (await db.execute(select(PayrollPeriod).where(PayrollPeriod.tenant_id == tenant_id).order_by(PayrollPeriod.start_date.desc()))).scalars().all()


@router.post("/periods/{period_id}/close")
async def close_payroll_period(period_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    period = (await db.execute(select(PayrollPeriod).where(
        PayrollPeriod.tenant_id == tenant_id, PayrollPeriod.payroll_period_id == period_id
    ))).scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found.")
    period.status = "CLOSED"
    await db.flush()
    return {"payroll_period_id": period.payroll_period_id, "status": period.status}


@router.post("/additional-salaries", status_code=status.HTTP_201_CREATED)
async def create_additional_salary(req: CreateAdditionalSalaryRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    row = AdditionalSalary(tenant_id=tenant_id, **req.model_dump(), status="PENDING")
    db.add(row)
    await db.flush()
    return row


@router.get("/additional-salaries")
async def list_additional_salaries(tenant_id: TenantIdDep, db: DbSessionDep):
    return (await db.execute(select(AdditionalSalary).where(AdditionalSalary.tenant_id == tenant_id).order_by(AdditionalSalary.payroll_date.desc()))).scalars().all()


@router.post("/retention-bonuses", status_code=status.HTTP_201_CREATED)
async def create_retention_bonus(req: CreateRetentionBonusRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    row = RetentionBonus(tenant_id=tenant_id, **req.model_dump(), status="PENDING")
    db.add(row)
    await db.flush()
    return row


@router.get("/retention-bonuses")
async def list_retention_bonuses(tenant_id: TenantIdDep, db: DbSessionDep):
    return (await db.execute(select(RetentionBonus).where(RetentionBonus.tenant_id == tenant_id).order_by(RetentionBonus.vesting_date.desc()))).scalars().all()


@router.post("/components", status_code=status.HTTP_201_CREATED, summary="Create salary component")
async def create_component(req: CreateComponentRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await payroll_service.create_salary_component(
        db, tenant_id, req.component_name, req.component_code, req.component_type,
        req.calculation_type, req.formula_expression, req.is_taxable, req.account_code
    )


@router.get("/components", summary="List salary components")
async def list_components(tenant_id: TenantIdDep, db: DbSessionDep):
    return await payroll_service.list_salary_components(db, tenant_id)


# Structures
@router.post("/structures", status_code=status.HTTP_201_CREATED, summary="Create salary structure")
async def create_structure(req: CreateStructureRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        items_dicts = [itm.model_dump() for itm in req.items]
        return await payroll_service.create_salary_structure(
            db, tenant_id, req.structure_name, items_dicts, req.payroll_frequency, req.currency
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/structures", summary="List salary structures")
async def list_structures(tenant_id: TenantIdDep, db: DbSessionDep):
    return await payroll_service.list_salary_structures(db, tenant_id)


# Structure Assignment
@router.post("/assignments", status_code=status.HTTP_201_CREATED, summary="Assign salary structure to employee")
async def assign_structure(req: AssignStructureRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    return await payroll_service.assign_salary_structure(
        db, tenant_id, req.employee_id, req.structure_id, req.from_date, req.base_salary
    )


# Individual Salary Slips
@router.post("/slips/generate", status_code=status.HTTP_201_CREATED, summary="Generate draft salary slip")
async def generate_salary_slip(req: GenerateSlipRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await payroll_service.generate_salary_slip(
            db, tenant_id, req.employee_id, req.posting_date, req.start_date, req.end_date
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/slips", summary="List salary slips")
async def list_salary_slips(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
):
    return await payroll_service.list_salary_slips(db, tenant_id, employee_id, status)


@router.get("/slips/{slip_id}", summary="Get salary slip details")
async def get_salary_slip(slip_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    slip = await payroll_service.get_salary_slip(db, tenant_id, slip_id)
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    return slip


@router.post("/slips/{slip_id}/submit", summary="Submit salary slip and post double-entry GL journal")
async def submit_salary_slip(slip_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await payroll_service.submit_salary_slip(db, tenant_id, slip_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Batch Payroll Processing
@router.post("/batches/generate", status_code=status.HTTP_201_CREATED, summary="Generate batch monthly payroll")
async def create_batch_payroll(req: CreateBatchPayrollRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        entry, slips = await batch_payroll_service.create_batch_payroll(
            db, tenant_id, req.posting_date, req.start_date, req.end_date, req.department_id
        )
        return {
            "payroll_entry": entry,
            "salary_slips_count": len(slips),
            "total_gross_pay": str(entry.total_gross_pay),
            "total_net_pay": str(entry.total_net_pay),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/batches", summary="List batch payroll entries")
async def list_batch_payrolls(tenant_id: TenantIdDep, db: DbSessionDep):
    return await batch_payroll_service.list_batch_payrolls(db, tenant_id)


@router.post("/batches/{batch_id}/submit", summary="Submit batch payroll and post mass GL journals")
async def submit_batch_payroll(batch_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await batch_payroll_service.submit_batch_payroll(db, tenant_id, batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
