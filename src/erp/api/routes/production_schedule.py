"""Production Scheduling and Dynamic Rescheduling API Endpoints."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.manufacturing import WorkOrder, Workstation
from erp.production.cpsat_scheduler import (
    JobOperationSpec,
    JobSpec,
    ScheduleResult,
    cpsat_scheduler,
)
from erp.production.router import RerouteEventResult, production_router

router = APIRouter(prefix="/production", tags=["Production & Shop Floor Scheduling"])


class CreateWorkstationRequest(BaseModel):
    workstation_code: str = Field(..., min_length=2, max_length=64)
    workstation_name: str = Field(..., min_length=2, max_length=128)
    hourly_rate: Decimal = Decimal("45.0000")
    status: str = "OPERATIONAL"


class CreateWorkOrderRequest(BaseModel):
    work_order_number: str = Field(..., min_length=2, max_length=64)
    item_id: uuid.UUID
    workstation_id: uuid.UUID | None = None
    planned_quantity: Decimal


class SolveScheduleRequest(BaseModel):
    jobs: list[JobSpec] = Field(default_factory=list)
    locked_workstations: list[str] = Field(default_factory=list)


class WorkstationFaultRequest(BaseModel):
    faulted_workstation_code: str = "WS-CNC-01"
    jobs: list[JobSpec] = Field(default_factory=list)


@router.get("/workstations", summary="List workstations")
async def list_workstations(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns workstations configured on the shop floor for the tenant."""
    stmt = (
        select(Workstation)
        .where(Workstation.tenant_id == tenant_id)
        .order_by(Workstation.workstation_code.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/workstations", status_code=status.HTTP_201_CREATED, summary="Create workstation")
async def create_workstation(
    req: CreateWorkstationRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Adds a new machine or cell to the factory workstation registry."""
    existing = (
        await db.execute(
            select(Workstation).where(
                Workstation.tenant_id == tenant_id,
                Workstation.workstation_code == req.workstation_code,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workstation with code '{req.workstation_code}' already exists.",
        )

    ws = Workstation(
        tenant_id=tenant_id,
        workstation_code=req.workstation_code,
        workstation_name=req.workstation_name,
        hourly_rate=req.hourly_rate,
        status=req.status,
        health_score=Decimal("100.00"),
        is_active=True,
    )
    db.add(ws)
    await db.flush()
    return ws


@router.get("/work-orders", summary="List work orders")
async def list_work_orders(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns production work orders for the tenant."""
    stmt = (
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id)
        .order_by(WorkOrder.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/work-orders", status_code=status.HTTP_201_CREATED, summary="Create work order")
async def create_work_order(req: CreateWorkOrderRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Creates a new production work order."""
    wo = WorkOrder(
        tenant_id=tenant_id,
        work_order_number=req.work_order_number,
        item_id=req.item_id,
        workstation_id=req.workstation_id,
        planned_quantity=req.planned_quantity,
        produced_quantity=Decimal("0.0000"),
        status="SCHEDULED",
    )
    db.add(wo)
    await db.flush()
    return wo


@router.post(
    "/solve-schedule",
    response_model=ScheduleResult,
    summary="Solve job-shop schedule with Google OR-Tools CP-SAT",
)
async def solve_production_schedule(
    req: SolveScheduleRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Computes global makespan-minimized schedule enforcing machine non-overlap constraints."""
    jobs_to_solve = req.jobs
    if not jobs_to_solve:
        # Load active work orders and workstations from PostgreSQL
        wo_stmt = select(WorkOrder).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(["SCHEDULED", "DRAFT", "IN_PROGRESS"]),
        )
        work_orders = (await db.execute(wo_stmt)).scalars().all()

        ws_stmt = select(Workstation).where(
            Workstation.tenant_id == tenant_id,
            Workstation.status == "OPERATIONAL",
        )
        workstations = (await db.execute(ws_stmt)).scalars().all()
        ws_codes = [ws.workstation_code for ws in workstations] or ["WS-CNC-01"]

        for wo in work_orders:
            ops = [
                JobOperationSpec(
                    operation_id=f"OP-{wo.work_order_number}-01",
                    operation_name=f"Machining for {wo.work_order_number}",
                    workstation_code=ws_codes[0],
                    duration_minutes=int(max(15, min(120, float(wo.planned_quantity) * 2))),
                    alternative_workstations=ws_codes[1:2],
                )
            ]
            jobs_to_solve.append(
                JobSpec(
                    job_id=wo.work_order_number,
                    job_name=f"Work Order {wo.work_order_number}",
                    operations=ops,
                )
            )

    if not jobs_to_solve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No production jobs provided or active work orders found to schedule.",
        )

    return cpsat_scheduler.solve_schedule(
        jobs=jobs_to_solve,
        locked_workstations=set(req.locked_workstations),
    )


@router.post(
    "/fault-reroute",
    response_model=RerouteEventResult,
    summary="Simulate workstation failure and trigger dynamic CP-SAT rerouting",
)
async def simulate_fault_and_reroute(
    req: WorkstationFaultRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Simulates edge machine fault, evacuates queue, and re-optimizes schedule across qualified machinery."""
    # Mark workstation as faulted in database
    ws = (
        await db.execute(
            select(Workstation).where(
                Workstation.tenant_id == tenant_id,
                Workstation.workstation_code == req.faulted_workstation_code,
            )
        )
    ).scalar_one_or_none()
    if ws:
        ws.status = "FAULT"
        ws.health_score = Decimal("25.00")
        await db.flush()

    jobs = req.jobs
    if not jobs:
        wo_stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
        work_orders = (await db.execute(wo_stmt)).scalars().all()
        for wo in work_orders:
            jobs.append(
                JobSpec(
                    job_id=wo.work_order_number,
                    job_name=f"Work Order {wo.work_order_number}",
                    operations=[
                        JobOperationSpec(
                            operation_id=f"OP-{wo.work_order_number}-01",
                            operation_name="Primary Operation",
                            workstation_code=req.faulted_workstation_code,
                            duration_minutes=45,
                            alternative_workstations=["WS-CNC-02"],
                        )
                    ],
                )
            )

    return production_router.handle_workstation_failure(
        faulted_workstation_code=req.faulted_workstation_code,
        current_jobs=jobs,
    )
