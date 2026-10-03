"""Preventive Maintenance Schedules, Machine Checklists & Dispatched Visits API."""

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.assets import Asset
from erp.workflows.maintenance import maintenance_service

router = APIRouter(prefix="/maintenance", tags=["Preventive Maintenance"])


# Schemas
class CreateScheduleSchema(BaseModel):
    schedule_number: Optional[str] = None
    periodicity: str = "MONTHLY"
    start_date: date
    task_description: Optional[str] = "Routine Periodic Inspection & Servicing"
    asset_id: Optional[Any] = None
    item_code: Optional[str] = None
    end_date: Optional[date] = None
    checklist_items: Optional[List[str]] = None


class CreateVisitSchema(BaseModel):
    visit_number: Optional[str] = None
    tasks_performed: Optional[str] = "Routine Maintenance Service"
    schedule_id: Optional[Any] = None
    asset_id: Optional[Any] = None
    technician_id: Optional[uuid.UUID] = None
    technician_name: Optional[str] = None
    technician: Optional[str] = None
    visit_date: Optional[date] = None
    maintenance_type: str = "PREVENTIVE"
    parts_replaced: Optional[Any] = None
    completion_remarks: Optional[str] = None
    downtime_hours: Decimal = Decimal("0.00")
    maintenance_cost: Decimal = Decimal("0.0000")
    status: str = "COMPLETED"


# Endpoints
@router.post("/schedules", status_code=status.HTTP_201_CREATED, summary="Create Maintenance Schedule")
async def create_schedule(req: CreateScheduleSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    sched_num = req.schedule_number or f"PMS-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    desc = req.task_description or "Routine Periodic Inspection & Servicing"

    parsed_asset_id: Optional[uuid.UUID] = None
    item_code = req.item_code
    if req.asset_id:
        try:
            parsed_asset_id = uuid.UUID(str(req.asset_id))
        except (ValueError, AttributeError):
            raw_val = str(req.asset_id).strip()
            lookup_stmt = select(Asset).where(
                Asset.tenant_id == tenant_id,
                (Asset.asset_code == raw_val) | (Asset.asset_name == raw_val),
            )
            matched_asset = (await db.execute(lookup_stmt)).scalar_one_or_none()
            if matched_asset:
                parsed_asset_id = matched_asset.asset_id
            else:
                item_code = item_code or raw_val

    sched = await maintenance_service.create_schedule(
        session=db,
        tenant_id=tenant_id,
        schedule_number=sched_num,
        periodicity=req.periodicity,
        start_date=req.start_date,
        task_description=desc,
        asset_id=parsed_asset_id,
        item_code=item_code,
        end_date=req.end_date,
        checklist_items=req.checklist_items,
    )
    return {
        "id": sched.schedule_id,
        "schedule_id": sched.schedule_id,
        "schedule_number": sched.schedule_number,
        "periodicity": sched.periodicity,
        "next_due_date": str(sched.next_due_date),
        "status": sched.status,
    }


@router.get("/schedules", summary="List Maintenance Schedules")
async def list_schedules(tenant_id: TenantIdDep, db: DbSessionDep, status: Optional[str] = Query(None)):
    scheds = await maintenance_service.list_schedules(db, tenant_id, status=status)
    asset_ids = [s.asset_id for s in scheds if s.asset_id]
    asset_map = {}
    if asset_ids:
        assets_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        for a in assets_res.scalars().all():
            asset_map[a.asset_id] = {"asset_name": a.asset_name, "asset_code": a.asset_code}

    return [
        {
            "id": s.schedule_id,
            "schedule_id": s.schedule_id,
            "schedule_number": s.schedule_number,
            "asset_id": s.asset_id,
            "asset": asset_map.get(s.asset_id),
            "item_code": s.item_code,
            "periodicity": s.periodicity,
            "start_date": str(s.start_date),
            "next_due_date": str(s.next_due_date),
            "end_date": str(s.end_date) if s.end_date else None,
            "task_description": s.task_description,
            "checklist_items": s.checklist_items,
            "status": s.status,
            "visit_count": len(s.visits),
        }
        for s in scheds
    ]


@router.get("/schedules/{schedule_id}", summary="Get Maintenance Schedule")
async def get_schedule(schedule_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    sched = await maintenance_service.get_schedule(db, tenant_id, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Maintenance Schedule not found")
    return {
        "id": sched.schedule_id,
        "schedule_id": sched.schedule_id,
        "schedule_number": sched.schedule_number,
        "asset_id": sched.asset_id,
        "item_code": sched.item_code,
        "periodicity": sched.periodicity,
        "start_date": str(sched.start_date),
        "next_due_date": str(sched.next_due_date),
        "task_description": sched.task_description,
        "checklist_items": sched.checklist_items,
        "status": sched.status,
        "visits": [
            {
                "id": v.visit_id,
                "visit_id": v.visit_id,
                "visit_number": v.visit_number,
                "visit_date": str(v.visit_date),
                "technician_name": v.technician_name,
                "tasks_performed": v.tasks_performed,
                "downtime_hours": float(v.downtime_hours),
                "maintenance_cost": float(v.maintenance_cost),
                "status": v.status,
            }
            for v in sched.visits
        ],
    }


@router.post("/visits", status_code=status.HTTP_201_CREATED, summary="Record Maintenance Visit")
async def record_visit(req: CreateVisitSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    v_num = req.visit_number or f"MNT-VISIT-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    tasks = req.tasks_performed or req.completion_remarks or "Routine Maintenance Service"
    tech_name = req.technician_name or req.technician or "Lead Technician"

    parsed_asset_id: Optional[uuid.UUID] = None
    if req.asset_id:
        try:
            parsed_asset_id = uuid.UUID(str(req.asset_id))
        except (ValueError, AttributeError):
            raw_val = str(req.asset_id).strip()
            lookup_stmt = select(Asset).where(
                Asset.tenant_id == tenant_id,
                (Asset.asset_code == raw_val) | (Asset.asset_name == raw_val),
            )
            matched_asset = (await db.execute(lookup_stmt)).scalar_one_or_none()
            if matched_asset:
                parsed_asset_id = matched_asset.asset_id

    parsed_sched_id: Optional[uuid.UUID] = None
    if req.schedule_id:
        try:
            parsed_sched_id = uuid.UUID(str(req.schedule_id))
        except (ValueError, AttributeError):
            parsed_sched_id = None

    parts_str = None
    if req.parts_replaced:
        if isinstance(req.parts_replaced, str):
            parts_str = req.parts_replaced
        else:
            try:
                parts_str = json.dumps(req.parts_replaced)
            except Exception:
                parts_str = str(req.parts_replaced)

    visit = await maintenance_service.record_visit(
        session=db,
        tenant_id=tenant_id,
        visit_number=v_num,
        tasks_performed=tasks,
        schedule_id=parsed_sched_id,
        asset_id=parsed_asset_id,
        technician_id=req.technician_id,
        technician_name=tech_name,
        visit_date=req.visit_date,
        maintenance_type=req.maintenance_type,
        parts_replaced=parts_str,
        downtime_hours=req.downtime_hours,
        maintenance_cost=req.maintenance_cost,
        status=req.status,
    )
    return {
        "id": visit.visit_id,
        "visit_id": visit.visit_id,
        "visit_number": visit.visit_number,
        "visit_date": str(visit.visit_date),
        "downtime_hours": float(visit.downtime_hours),
        "maintenance_cost": float(visit.maintenance_cost),
        "status": visit.status,
    }


@router.get("/visits", summary="List Maintenance Visits")
async def list_visits(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    asset_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
):
    visits = await maintenance_service.list_visits(db, tenant_id, asset_id=asset_id, status=status)
    asset_ids = [v.asset_id for v in visits if v.asset_id]
    asset_map = {}
    if asset_ids:
        assets_res = await db.execute(select(Asset).where(Asset.asset_id.in_(asset_ids)))
        for a in assets_res.scalars().all():
            asset_map[a.asset_id] = {"asset_name": a.asset_name, "asset_code": a.asset_code}

    def parse_parts(p):
        if not p:
            return []
        if isinstance(p, list):
            return p
        try:
            return json.loads(p)
        except Exception:
            return [{"item_code": p, "qty": 1}]

    return [
        {
            "id": v.visit_id,
            "visit_id": v.visit_id,
            "visit_number": v.visit_number,
            "schedule_id": v.schedule_id,
            "asset_id": v.asset_id,
            "asset": asset_map.get(v.asset_id),
            "technician": v.technician_name,
            "technician_name": v.technician_name,
            "visit_date": str(v.visit_date),
            "maintenance_type": v.maintenance_type,
            "tasks_performed": v.tasks_performed,
            "completion_remarks": v.tasks_performed,
            "parts_replaced": parse_parts(v.parts_replaced),
            "downtime_hours": float(v.downtime_hours),
            "maintenance_cost": float(v.maintenance_cost),
            "status": v.status,
        }
        for v in visits
    ]
