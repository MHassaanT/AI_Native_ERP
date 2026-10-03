"""Payroll & Compensation Management API Routes."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
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


# --- Endpoints ---

# Components
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
