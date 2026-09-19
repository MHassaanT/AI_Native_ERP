from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.manufacturing import BOM, WorkOrder, Workstation
from erp.ledger.engine import TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
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
    bom_id: uuid.UUID | None = None
    workstation_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None
    planned_quantity: Decimal


class CompleteWorkOrderRequest(BaseModel):
    produced_quantity: Decimal | None = None
    warehouse_id: uuid.UUID | None = None


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
    """Creates a new production work order and reserves required BOM component raw materials."""
    # Find active BOM for item if not explicitly supplied
    bom = None
    if req.bom_id:
        bom_stmt = (
            select(BOM)
            .options(selectinload(BOM.items))
            .where(
                BOM.tenant_id == tenant_id,
                BOM.bom_id == req.bom_id,
            )
        )
        bom = (await db.execute(bom_stmt)).scalar_one_or_none()
    else:
        bom_stmt = (
            select(BOM)
            .options(selectinload(BOM.items))
            .where(
                BOM.tenant_id == tenant_id,
                BOM.item_id == req.item_id,
                BOM.is_active.is_(True),
            )
        )
        bom = (await db.execute(bom_stmt)).scalars().first()

    # Find warehouse for reservation
    wh_id = req.warehouse_id
    if not wh_id:
        wh = (
            await db.execute(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.is_active.is_(True),
                )
            )
        ).scalars().first()
        if wh:
            wh_id = wh.warehouse_id

    # Reserve raw materials in StockLevel if BOM items exist and warehouse found
    if bom and bom.items and wh_id:
        base_qty = bom.quantity if bom.quantity > 0 else Decimal("1.0000")
        for b_item in bom.items:
            comp_req_qty = (b_item.quantity / base_qty) * req.planned_quantity
            stk = (
                await db.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == b_item.item_id,
                        StockLevel.warehouse_id == wh_id,
                    )
                )
            ).scalar_one_or_none()

            if stk:
                stk.reserved_qty += comp_req_qty
                stk.available_qty = stk.current_qty - stk.reserved_qty
            else:
                stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=b_item.item_id,
                    warehouse_id=wh_id,
                    current_qty=Decimal("0.0000"),
                    reserved_qty=comp_req_qty,
                    available_qty=-comp_req_qty,
                    valuation_rate=b_item.rate if b_item.rate > 0 else Decimal("10.0000"),
                )
                db.add(stk)

    wo = WorkOrder(
        tenant_id=tenant_id,
        work_order_number=req.work_order_number,
        item_id=req.item_id,
        bom_id=bom.bom_id if bom else req.bom_id,
        workstation_id=req.workstation_id,
        planned_quantity=req.planned_quantity,
        produced_quantity=Decimal("0.0000"),
        status="SCHEDULED",
    )
    db.add(wo)
    await db.flush()
    return wo


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
    """Marks work order completed, deducts raw materials, records finished goods SLE, and posts GL valuation transfer."""
    wo_stmt = select(WorkOrder).where(
        WorkOrder.tenant_id == tenant_id,
        WorkOrder.work_order_id == work_order_id,
    )
    wo = (await db.execute(wo_stmt)).scalar_one_or_none()
    if not wo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order '{work_order_id}' not found.",
        )
    if wo.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Work order is already completed.",
        )

    produced_qty = req.produced_quantity or wo.planned_quantity

    # Determine warehouse
    wh_id = req.warehouse_id
    if not wh_id:
        wh = (
            await db.execute(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.is_active.is_(True),
                )
            )
        ).scalars().first()
        if wh:
            wh_id = wh.warehouse_id

    if not wh_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active warehouse found for inventory transactions.",
        )

    # Load BOM
    bom = None
    if wo.bom_id:
        bom_stmt = (
            select(BOM)
            .options(selectinload(BOM.items))
            .where(
                BOM.tenant_id == tenant_id,
                BOM.bom_id == wo.bom_id,
            )
        )
        bom = (await db.execute(bom_stmt)).scalar_one_or_none()
    if not bom:
        bom_stmt = (
            select(BOM)
            .options(selectinload(BOM.items))
            .where(
                BOM.tenant_id == tenant_id,
                BOM.item_id == wo.item_id,
                BOM.is_active.is_(True),
            )
        )
        bom = (await db.execute(bom_stmt)).scalars().first()

    total_component_cost = Decimal("0.0000")
    now_utc = datetime.now(UTC)

    if bom and bom.items:
        base_qty = bom.quantity if bom.quantity > 0 else Decimal("1.0000")
        for b_item in bom.items:
            consumed_qty = (b_item.quantity / base_qty) * produced_qty
            rate = b_item.rate if b_item.rate > 0 else (
                (b_item.amount / b_item.quantity) if b_item.quantity > 0 else Decimal("10.0000")
            )
            line_cost = consumed_qty * rate
            total_component_cost += line_cost

            # Deduct component from StockLevel
            stk = (
                await db.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == b_item.item_id,
                        StockLevel.warehouse_id == wh_id,
                    )
                )
            ).scalar_one_or_none()

            if stk:
                stk.current_qty -= consumed_qty
                stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - consumed_qty)
                stk.available_qty = stk.current_qty - stk.reserved_qty
                qty_after = stk.current_qty
            else:
                qty_after = -consumed_qty

            # Write StockLedgerEntry for WORK_ORDER_ISSUE
            sle_issue = StockLedgerEntry(
                tenant_id=tenant_id,
                posting_datetime=now_utc,
                item_id=b_item.item_id,
                warehouse_id=wh_id,
                actual_qty=-consumed_qty,
                qty_after_transaction=qty_after,
                outgoing_rate=rate,
                valuation_rate=rate,
                stock_value_difference=-line_cost,
                source_document_type="WORK_ORDER_ISSUE",
                source_document_id=wo.work_order_id,
            )
            db.add(sle_issue)

    if total_component_cost <= Decimal("0.0000"):
        total_component_cost = produced_qty * Decimal("25.0000")

    fg_unit_rate = total_component_cost / max(produced_qty, Decimal("1.0000"))

    # Add finished good to StockLevel
    fg_stk = (
        await db.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == wo.item_id,
                StockLevel.warehouse_id == wh_id,
            )
        )
    ).scalar_one_or_none()

    if fg_stk:
        fg_stk.current_qty += produced_qty
        fg_stk.available_qty = fg_stk.current_qty - fg_stk.reserved_qty
        fg_stk.valuation_rate = fg_unit_rate
        fg_after = fg_stk.current_qty
    else:
        fg_stk = StockLevel(
            tenant_id=tenant_id,
            item_id=wo.item_id,
            warehouse_id=wh_id,
            current_qty=produced_qty,
            reserved_qty=Decimal("0.0000"),
            available_qty=produced_qty,
            valuation_rate=fg_unit_rate,
        )
        db.add(fg_stk)
        fg_after = produced_qty

    # Write StockLedgerEntry for WORK_ORDER_RECEIPT
    sle_receipt = StockLedgerEntry(
        tenant_id=tenant_id,
        posting_datetime=now_utc,
        item_id=wo.item_id,
        warehouse_id=wh_id,
        actual_qty=produced_qty,
        qty_after_transaction=fg_after,
        incoming_rate=fg_unit_rate,
        valuation_rate=fg_unit_rate,
        stock_value_difference=total_component_cost,
        source_document_type="WORK_ORDER_RECEIPT",
        source_document_id=wo.work_order_id,
    )
    db.add(sle_receipt)

    # Post GL Valuation Transfer: Dr 1350-FINISHED-GOODS / Cr 1300-RAW-MATERIALS
    entries = [
        LedgerLineProposal(
            account_code="1350-FINISHED-GOODS",
            cost_center="MFG-PLANT-01",
            debit_amount=total_component_cost,
            credit_amount=Decimal("0.0000"),
            currency="USD",
        ),
        LedgerLineProposal(
            account_code="1300-RAW-MATERIALS",
            cost_center="MFG-PLANT-01",
            debit_amount=Decimal("0.0000"),
            credit_amount=total_component_cost,
            currency="USD",
        ),
    ]
    proposal = TransactionProposal(
        tenant_id=tenant_id,
        posting_date=date.today(),
        currency="USD",
        source_document_type="WORK_ORDER_COMPLETION",
        source_document_id=wo.work_order_id,
        entries=entries,
        human_in_the_loop_approved=False,
        agent_id="PRODUCTION_CONTROLLER",
        verification_context={"work_order_number": wo.work_order_number},
    )
    await ledger_engine.commit_transaction(session=db, proposal=proposal)

    wo.status = "COMPLETED"
    wo.produced_quantity = produced_qty
    await db.flush()

    return {
        "work_order_id": str(wo.work_order_id),
        "work_order_number": wo.work_order_number,
        "status": wo.status,
        "produced_quantity": str(wo.produced_quantity),
        "valuation_transferred": str(total_component_cost),
    }



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
