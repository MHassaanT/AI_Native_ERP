"""Production & Shop Floor Execution (MES) API Routes."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.manufacturing import BOM, DowntimeEntry, JobCard, Operation, ProductionPlan, Routing, WorkOrder, Workstation
from erp.production.cpsat_scheduler import (
    JobOperationSpec,
    JobSpec,
    ScheduleResult,
    cpsat_scheduler,
)
from erp.production.router import RerouteEventResult, production_router
from erp.workflows.manufacturing.bom_service import bom_service
from erp.workflows.manufacturing.job_card_service import job_card_service
from erp.workflows.manufacturing.mrp_service import mrp_service
from erp.workflows.manufacturing.oee_service import oee_service
from erp.workflows.manufacturing.work_order_service import work_order_service

router = APIRouter(prefix="/production", tags=["Production & Shop Floor Scheduling"])


# --- Pydantic Schemas ---

class CreateWorkstationRequest(BaseModel):
    workstation_code: str = Field(..., min_length=2, max_length=64)
    workstation_name: str = Field(..., min_length=2, max_length=128)
    workstation_type: str = "GENERAL"
    hourly_rate: Decimal = Decimal("45.0000")
    electricity_cost_per_hour: Decimal = Decimal("0.0000")
    consumable_cost_per_hour: Decimal = Decimal("0.0000")
    rent_per_hour: Decimal = Decimal("0.0000")
    production_capacity: Decimal = Decimal("1.0000")
    status: str = "OPERATIONAL"


class CreateOperationRequest(BaseModel):
    operation_name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None
    default_workstation_id: uuid.UUID | None = None


class RoutingOperationItemSchema(BaseModel):
    operation_id: uuid.UUID
    workstation_id: uuid.UUID | None = None
    sequence_id: int = 1
    time_in_mins: Decimal = Decimal("15.0000")
    hourly_rate: Decimal = Decimal("0.0000")
    batch_size: Decimal = Decimal("1.0000")


class CreateRoutingRequest(BaseModel):
    routing_name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None
    operations: list[RoutingOperationItemSchema] = Field(default_factory=list)


class BOMItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    rate: Decimal = Decimal("0.0000")
    bom_sub_assembly_id: uuid.UUID | None = None
    operation_id: uuid.UUID | None = None
    scrap_percentage: Decimal = Decimal("0.00")


class BOMOperationSchema(BaseModel):
    operation_id: uuid.UUID
    workstation_id: uuid.UUID | None = None
    sequence_id: int = 1
    time_in_mins: Decimal = Decimal("15.0000")
    hourly_rate: Decimal = Decimal("0.0000")
    batch_size: Decimal = Decimal("1.0000")


class BOMScrapSchema(BaseModel):
    item_id: uuid.UUID
    stock_qty: Decimal = Decimal("0.0000")
    rate: Decimal = Decimal("0.0000")


class CreateBOMRequest(BaseModel):
    bom_number: str = Field(..., min_length=2, max_length=64)
    item_id: uuid.UUID
    quantity: Decimal = Decimal("1.0000")
    routing_id: uuid.UUID | None = None
    with_operations: bool = False
    is_default: bool = True
    items: list[BOMItemSchema] = Field(default_factory=list)
    operations: list[BOMOperationSchema] = Field(default_factory=list)
    scrap_items: list[BOMScrapSchema] = Field(default_factory=list)


class ProductionPlanItemSchema(BaseModel):
    item_id: uuid.UUID
    planned_qty: Decimal
    bom_id: uuid.UUID | None = None
    sales_order_id: uuid.UUID | None = None


class CreateProductionPlanRequest(BaseModel):
    plan_number: str = Field(..., min_length=2, max_length=64)
    posting_date: date | None = None
    items: list[ProductionPlanItemSchema]


class CreateWorkOrderRequest(BaseModel):
    work_order_number: str = Field(..., min_length=2, max_length=64)
    item_id: uuid.UUID
    bom_id: uuid.UUID | None = None
    workstation_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None
    source_warehouse_id: uuid.UUID | None = None
    wip_warehouse_id: uuid.UUID | None = None
    fg_warehouse_id: uuid.UUID | None = None
    scrap_warehouse_id: uuid.UUID | None = None
    planned_quantity: Decimal
    production_plan_id: uuid.UUID | None = None


class CompleteWorkOrderRequest(BaseModel):
    produced_quantity: Decimal | None = None
    scrap_quantity: Decimal | None = None
    warehouse_id: uuid.UUID | None = None


class StartJobCardRequest(BaseModel):
    employee_id: uuid.UUID | None = None


class PauseOrCompleteJobCardRequest(BaseModel):
    employee_id: uuid.UUID | None = None
    completed_qty: Decimal = Decimal("0.0000")
    scrap_qty: Decimal = Decimal("0.0000")


class RecordDowntimeRequest(BaseModel):
    downtime_number: str = Field(..., min_length=2, max_length=64)
    workstation_id: uuid.UUID
    reason: str = "MECHANICAL_BREAKDOWN"
    fault_code: str | None = None
    operator_id: uuid.UUID | None = None
    notes: str | None = None


class SolveScheduleRequest(BaseModel):
    jobs: list[JobSpec] = Field(default_factory=list)
    locked_workstations: list[str] = Field(default_factory=list)


class WorkstationFaultRequest(BaseModel):
    faulted_workstation_code: str = "WS-CNC-01"
    jobs: list[JobSpec] = Field(default_factory=list)


# --- Workstation Endpoints ---

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
        workstation_type=req.workstation_type,
        hourly_rate=req.hourly_rate,
        electricity_cost_per_hour=req.electricity_cost_per_hour,
        consumable_cost_per_hour=req.consumable_cost_per_hour,
        rent_per_hour=req.rent_per_hour,
        production_capacity=req.production_capacity,
        status=req.status,
        health_score=Decimal("100.00"),
        is_active=True,
    )
    db.add(ws)
    await db.flush()
    return ws


@router.get("/workstations/{workstation_id}/oee", summary="Get Workstation OEE Telemetry")
async def get_workstation_oee(
    workstation_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    planned_minutes: float = Query(480.0, description="Shift planned production minutes"),
):
    """Calculates Availability, Performance, Quality, and composite OEE percentage."""
    try:
        return await oee_service.calculate_workstation_oee(
            session=db,
            tenant_id=tenant_id,
            workstation_id=workstation_id,
            planned_production_minutes=planned_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Operations Catalog Endpoints ---

@router.get("/operations", summary="List Operations")
async def list_operations(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists standard operations catalog."""
    return await bom_service.list_operations(session=db, tenant_id=tenant_id)


@router.post("/operations", status_code=status.HTTP_201_CREATED, summary="Create Operation")
async def create_operation(
    req: CreateOperationRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Registers an operation in the catalog."""
    return await bom_service.create_operation(
        session=db,
        tenant_id=tenant_id,
        operation_name=req.operation_name,
        description=req.description,
        default_workstation_id=req.default_workstation_id,
    )


# --- Routings Endpoints ---

@router.get("/routings", summary="List Routings")
async def list_routings(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists production routings."""
    return await bom_service.list_routings(session=db, tenant_id=tenant_id)


@router.post("/routings", status_code=status.HTTP_201_CREATED, summary="Create Routing")
async def create_routing(
    req: CreateRoutingRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Creates a routing with sequenced operations."""
    ops = [it.model_dump() for it in req.operations]
    return await bom_service.create_routing(
        session=db,
        tenant_id=tenant_id,
        routing_name=req.routing_name,
        description=req.description,
        operations=ops,
    )


@router.get("/routings/{routing_id}", summary="Get Routing Details")
async def get_routing(routing_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Retrieves routing sequence details."""
    routing = await bom_service.get_routing(session=db, tenant_id=tenant_id, routing_id=routing_id)
    if not routing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing not found.")
    return routing


# --- BOM (Bill of Materials) Endpoints ---

@router.get("/boms", summary="List BOMs")
async def list_boms(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    item_id: uuid.UUID | None = None,
):
    """Lists Bills of Materials."""
    return await bom_service.list_boms(session=db, tenant_id=tenant_id, item_id=item_id)


@router.post("/boms", status_code=status.HTTP_201_CREATED, summary="Create BOM")
async def create_bom(
    req: CreateBOMRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Creates a multi-level Bill of Materials with unit cost rollup."""
    items = [it.model_dump() for it in req.items]
    ops = [op.model_dump() for op in req.operations]
    scraps = [sc.model_dump() for sc in req.scrap_items]

    return await bom_service.create_bom(
        session=db,
        tenant_id=tenant_id,
        bom_number=req.bom_number,
        item_id=req.item_id,
        quantity=req.quantity,
        routing_id=req.routing_id,
        with_operations=req.with_operations,
        is_default=req.is_default,
        items=items,
        operations=ops,
        scrap_items=scraps,
    )


@router.get("/boms/{bom_id}", summary="Get BOM Details")
async def get_bom(bom_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Retrieves BOM with component lines, operations, and scraps."""
    bom = await bom_service.get_bom(session=db, tenant_id=tenant_id, bom_id=bom_id)
    if not bom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM not found.")
    return bom


@router.get("/boms/{bom_id}/tree", summary="Get Multi-Level BOM Tree")
async def get_bom_tree(bom_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns exploded multi-level hierarchical tree structure for visual BOM explorer."""
    tree = await bom_service.get_bom_tree(session=db, tenant_id=tenant_id, bom_id=bom_id)
    if not tree:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM not found or tree failed.")
    return tree


# --- Production Plans (MRP) Endpoints ---

@router.get("/plans", summary="List Production Plans")
async def list_production_plans(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status_filter: str | None = Query(None, alias="status"),
):
    """Lists Production Plans."""
    return await mrp_service.list_production_plans(session=db, tenant_id=tenant_id, status=status_filter)


@router.post("/plans", status_code=status.HTTP_201_CREATED, summary="Create Production Plan")
async def create_production_plan(
    req: CreateProductionPlanRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Creates a new Production Plan (MRP header)."""
    items = [it.model_dump() for it in req.items]
    return await mrp_service.create_production_plan(
        session=db,
        tenant_id=tenant_id,
        plan_number=req.plan_number,
        items=items,
        posting_date=req.posting_date,
    )


@router.get("/plans/{plan_id}", summary="Get Production Plan")
async def get_production_plan(plan_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Retrieves Production Plan with line items."""
    plan = await mrp_service.get_production_plan(session=db, tenant_id=tenant_id, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production Plan not found.")
    return plan


@router.get("/plans/{plan_id}/shortages", summary="Explode Material Requirements and Shortages")
async def get_production_plan_shortages(plan_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Explodes multi-level BOMs and checks stock across warehouses to determine shortages."""
    try:
        return await mrp_service.explode_material_requirements(session=db, tenant_id=tenant_id, plan_id=plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/plans/{plan_id}/create-work-orders", summary="Generate Work Orders from Plan")
async def generate_work_orders_from_plan(plan_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Generates Work Orders for all line items in the production plan."""
    try:
        return await mrp_service.generate_work_orders_from_plan(session=db, tenant_id=tenant_id, plan_id=plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Work Orders Endpoints ---

@router.get("/work-orders", summary="List work orders")
async def list_work_orders(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status_filter: str | None = Query(None, alias="status"),
):
    """Returns production work orders for the tenant."""
    return await work_order_service.list_work_orders(session=db, tenant_id=tenant_id, status=status_filter)


@router.post("/work-orders", status_code=status.HTTP_201_CREATED, summary="Create work order")
async def create_work_order(
    req: CreateWorkOrderRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Creates a new production work order and generates Job Cards."""
    return await work_order_service.create_work_order(
        session=db,
        tenant_id=tenant_id,
        work_order_number=req.work_order_number,
        item_id=req.item_id,
        planned_quantity=req.planned_quantity,
        bom_id=req.bom_id,
        workstation_id=req.workstation_id,
        source_warehouse_id=req.source_warehouse_id or req.warehouse_id,
        wip_warehouse_id=req.wip_warehouse_id,
        fg_warehouse_id=req.fg_warehouse_id,
        scrap_warehouse_id=req.scrap_warehouse_id,
        production_plan_id=req.production_plan_id,
    )


@router.get("/work-orders/{work_order_id}", summary="Get Work Order Details")
async def get_work_order(work_order_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Retrieves Work Order with travelers and logs."""
    wo = await work_order_service.get_work_order(session=db, tenant_id=tenant_id, work_order_id=work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work Order not found.")
    return wo


@router.post("/work-orders/{work_order_id}/stage-materials", summary="Stage Materials to WIP")
async def stage_work_order_materials(
    work_order_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Issues raw materials from Stores warehouse to WIP warehouse via StockEntry (ST-MAT-TRANSFER)."""
    try:
        return await work_order_service.stage_materials_to_wip(
            session=db, tenant_id=tenant_id, work_order_id=work_order_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/work-orders/{work_order_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Complete work order, issue raw materials, receive finished goods, and post GL transfer",
)
async def complete_work_order(
    work_order_id: uuid.UUID,
    req: CompleteWorkOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Completes work order, consumes WIP stock, adds FG stock, and posts balanced GL entries."""
    try:
        return await work_order_service.complete_manufacture(
            session=db,
            tenant_id=tenant_id,
            work_order_id=work_order_id,
            produced_quantity=req.produced_quantity,
            scrap_quantity=req.scrap_quantity,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Shop Floor MES & Job Cards Endpoints ---

@router.get("/job-cards", summary="List Job Cards")
async def list_job_cards(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    work_order_id: uuid.UUID | None = None,
    workstation_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    """Lists Job Cards with optional filters for shop floor operator console."""
    return await job_card_service.list_job_cards(
        session=db,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        workstation_id=workstation_id,
        employee_id=employee_id,
        status=status_filter,
    )


@router.get("/job-cards/{job_card_id}", summary="Get Job Card Details")
async def get_job_card(job_card_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    """Retrieves Job Card with punch clock session logs."""
    jc = await job_card_service.get_job_card(session=db, tenant_id=tenant_id, job_card_id=job_card_id)
    if not jc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job Card not found.")
    return jc


@router.post("/job-cards/{job_card_id}/start", summary="Start Job Card Timer (Punch IN)")
async def start_job_card(
    job_card_id: uuid.UUID,
    req: StartJobCardRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Punches IN on an operation traveler and starts the active session clock."""
    try:
        return await job_card_service.start_job_card(
            session=db,
            tenant_id=tenant_id,
            job_card_id=job_card_id,
            employee_id=req.employee_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/job-cards/{job_card_id}/pause", summary="Pause Job Card Timer (Punch OUT)")
async def pause_job_card(
    job_card_id: uuid.UUID,
    req: PauseOrCompleteJobCardRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Pauses punch clock session and records completed/scrap quantities produced so far."""
    try:
        return await job_card_service.pause_job_card(
            session=db,
            tenant_id=tenant_id,
            job_card_id=job_card_id,
            employee_id=req.employee_id,
            completed_qty=req.completed_qty,
            scrap_qty=req.scrap_qty,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/job-cards/{job_card_id}/complete", summary="Complete Job Card Operation")
async def complete_job_card(
    job_card_id: uuid.UUID,
    req: PauseOrCompleteJobCardRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Marks traveler operation complete, records final time log, and frees the workstation."""
    try:
        return await job_card_service.complete_job_card(
            session=db,
            tenant_id=tenant_id,
            job_card_id=job_card_id,
            employee_id=req.employee_id,
            completed_qty=req.completed_qty,
            scrap_qty=req.scrap_qty,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Downtime Logging Endpoints ---

@router.get("/downtimes", summary="List Machine Downtimes")
async def list_downtimes(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    workstation_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    """Lists recorded machine stoppages and breakdown entries."""
    return await oee_service.list_downtimes(
        session=db, tenant_id=tenant_id, workstation_id=workstation_id, status=status_filter
    )


@router.post("/downtimes", status_code=status.HTTP_201_CREATED, summary="Record Downtime")
async def record_downtime(
    req: RecordDowntimeRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Logs an unplanned stop, setting workstation status to FAULT / MAINTENANCE."""
    try:
        return await oee_service.record_downtime(
            session=db,
            tenant_id=tenant_id,
            downtime_number=req.downtime_number,
            workstation_id=req.workstation_id,
            reason=req.reason,
            fault_code=req.fault_code,
            operator_id=req.operator_id,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/downtimes/{downtime_id}/resolve", summary="Resolve Downtime")
async def resolve_downtime(
    downtime_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Resolves machine breakdown, logs duration, and restores workstation to OPERATIONAL."""
    try:
        return await oee_service.resolve_downtime(
            session=db, tenant_id=tenant_id, downtime_id=downtime_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- CP-SAT Scheduling & Dynamic Reroute Endpoints ---

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
            WorkOrder.status.in_(["SCHEDULED", "DRAFT", "IN_PROCESS", "IN_PROGRESS"]),
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
        jobs_to_solve = [
            JobSpec(
                job_id="WO-BASELINE-01",
                job_name="Production Job WO-BASELINE-01",
                operations=[
                    JobOperationSpec(
                        operation_id="OP-01",
                        operation_name="Precision Machining",
                        workstation_code=ws_codes[0] if ws_codes else "WS-CNC-01",
                        duration_minutes=45,
                        alternative_workstations=ws_codes[1:2] if len(ws_codes) > 1 else [],
                    )
                ],
            )
        ]

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
