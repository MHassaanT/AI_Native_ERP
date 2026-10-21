"""Project Master, Discrete Tasks, and Timesheet Cost/Billing Aggregation API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.projects import project_service

router = APIRouter(prefix="/projects", tags=["Projects & Timesheets"])


# Schemas
class CreateProjectSchema(BaseModel):
    project_code: str
    project_name: str
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    estimated_cost: Decimal = Decimal("0.0000")
    notes: Optional[str] = None
    project_type_id: uuid.UUID | None = None


class CreateTaskSchema(BaseModel):
    task_title: str
    task_description: Optional[str] = None
    priority: str = "MEDIUM"
    estimated_hours: Decimal = Decimal("0.00")
    assigned_to_id: Optional[uuid.UUID] = None
    assigned_to_name: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None


class UpdateTaskSchema(BaseModel):
    status: Optional[str] = None
    actual_hours: Optional[Decimal] = None


class CreateTimesheetSchema(BaseModel):
    timesheet_number: str
    employee_id: uuid.UUID
    hours: Decimal
    billing_rate: Decimal | None = None
    costing_rate: Decimal | None = None
    task_id: Optional[uuid.UUID] = None
    employee_name: Optional[str] = None
    activity_type: str = "ENGINEERING"
    work_date: Optional[date] = None
    is_billable: bool = True
    notes: Optional[str] = None
    activity_type_id: uuid.UUID | None = None


class CreateProjectTypeSchema(BaseModel):
    type_name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None


class CreateActivityTypeSchema(BaseModel):
    activity_name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None


class CreateActivityCostSchema(BaseModel):
    activity_type_id: uuid.UUID
    employee_id: uuid.UUID | None = None
    billing_rate: Decimal = Field(..., ge=0)
    costing_rate: Decimal = Field(..., ge=0)
    valid_from: date
    valid_to: date | None = None


class CreateProjectUpdateSchema(BaseModel):
    sender_email: str = Field(..., min_length=3, max_length=320)
    notes: str = Field(..., min_length=1)
    progress_pct: int | None = Field(None, ge=0, le=100)
    blockers: str | None = None


# Endpoints
@router.post("", status_code=status.HTTP_201_CREATED, summary="Create Project")
async def create_project(req: CreateProjectSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        proj = await project_service.create_project(
            session=db,
            tenant_id=tenant_id,
            project_code=req.project_code,
            project_name=req.project_name,
            customer_id=req.customer_id,
            customer_name=req.customer_name,
            start_date=req.start_date,
            end_date=req.end_date,
            estimated_cost=req.estimated_cost,
            notes=req.notes,
            project_type_id=req.project_type_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "project_id": proj.project_id,
        "project_code": proj.project_code,
        "project_name": proj.project_name,
        "estimated_cost": float(proj.estimated_cost),
        "actual_cost": float(proj.actual_cost),
        "percent_complete": float(proj.percent_complete),
        "status": proj.status,
    }


@router.get("", summary="List Projects")
async def list_projects(tenant_id: TenantIdDep, db: DbSessionDep, status: Optional[str] = Query(None)):
    projs = await project_service.list_projects(db, tenant_id, status=status)
    return [
        {
            "project_id": p.project_id,
            "project_code": p.project_code,
            "project_name": p.project_name,
            "project_type_id": p.project_type_id,
            "project_type_name": p.project_type.type_name if p.project_type else None,
            "customer_name": p.customer_name,
            "start_date": str(p.start_date),
            "estimated_cost": float(p.estimated_cost),
            "actual_cost": float(p.actual_cost),
            "total_billed_amount": float(p.total_billed_amount),
            "percent_complete": float(p.percent_complete),
            "status": p.status,
            "task_count": len(p.tasks),
            "timesheet_count": len(p.timesheets),
        }
        for p in projs
    ]


@router.get("/timesheets", summary="List Timesheets")
async def list_timesheets(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    project_id: Optional[uuid.UUID] = Query(None),
    employee_id: Optional[uuid.UUID] = Query(None),
):
    ts_list = await project_service.list_timesheets(db, tenant_id, project_id=project_id, employee_id=employee_id)
    return [
        {
            "timesheet_id": ts.timesheet_id,
            "timesheet_number": ts.timesheet_number,
            "employee_id": ts.employee_id,
            "employee_name": ts.employee_name,
            "project_id": ts.project_id,
            "activity_type": ts.activity_type,
            "work_date": str(ts.work_date),
            "hours": float(ts.hours),
            "billing_amount": float(ts.billing_amount),
            "costing_amount": float(ts.costing_amount),
            "is_billable": ts.is_billable,
            "status": ts.status,
        }
        for ts in ts_list
    ]


@router.post("/types", status_code=status.HTTP_201_CREATED)
async def create_project_type(req: CreateProjectTypeSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await project_service.create_project_type(db, tenant_id, req.type_name, req.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/types")
async def list_project_types(tenant_id: TenantIdDep, db: DbSessionDep):
    return await project_service.list_project_types(db, tenant_id)


@router.post("/activity-types", status_code=status.HTTP_201_CREATED)
async def create_activity_type(req: CreateActivityTypeSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await project_service.create_activity_type(db, tenant_id, req.activity_name, req.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/activity-types")
async def list_activity_types(tenant_id: TenantIdDep, db: DbSessionDep):
    return await project_service.list_activity_types(db, tenant_id)


@router.post("/activity-costs", status_code=status.HTTP_201_CREATED)
async def create_activity_cost(req: CreateActivityCostSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        return await project_service.create_activity_cost(db, tenant_id, **req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/activity-costs")
async def list_activity_costs(tenant_id: TenantIdDep, db: DbSessionDep):
    rows = await project_service.list_activity_costs(db, tenant_id)
    return [{"activity_cost_id": row.activity_cost_id, "activity_type_id": row.activity_type_id,
             "activity_name": row.activity_type.activity_name if row.activity_type else None,
             "employee_id": row.employee_id, "billing_rate": row.billing_rate, "costing_rate": row.costing_rate,
             "valid_from": row.valid_from, "valid_to": row.valid_to} for row in rows]


@router.get("/{project_id}", summary="Get Project Details with Tasks and Timesheets")
async def get_project(project_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    proj = await project_service.get_project(db, tenant_id, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": proj.project_id,
        "project_code": proj.project_code,
        "project_name": proj.project_name,
        "customer_name": proj.customer_name,
        "start_date": str(proj.start_date),
        "end_date": str(proj.end_date) if proj.end_date else None,
        "estimated_cost": float(proj.estimated_cost),
        "actual_cost": float(proj.actual_cost),
        "total_billed_amount": float(proj.total_billed_amount),
        "percent_complete": float(proj.percent_complete),
        "status": proj.status,
        "project_type_id": proj.project_type_id,
        "project_type_name": proj.project_type.type_name if proj.project_type else None,
        "tasks": [
            {
                "task_id": t.task_id,
                "task_title": t.task_title,
                "priority": t.priority,
                "status": t.status,
                "estimated_hours": float(t.estimated_hours),
                "actual_hours": float(t.actual_hours),
                "assigned_to_name": t.assigned_to_name,
                "due_date": str(t.due_date) if t.due_date else None,
            }
            for t in proj.tasks
        ],
        "timesheets": [
            {
                "timesheet_id": ts.timesheet_id,
                "timesheet_number": ts.timesheet_number,
                "employee_name": ts.employee_name,
                "activity_type": ts.activity_type,
                "work_date": str(ts.work_date),
                "hours": float(ts.hours),
                "billing_amount": float(ts.billing_amount),
                "costing_amount": float(ts.costing_amount),
                "is_billable": ts.is_billable,
            }
            for ts in proj.timesheets
        ],
        "updates": [{"update_id": u.update_id, "sender_email": u.sender_email,
                     "progress_pct": u.progress_pct, "notes": u.notes, "blockers": u.blockers,
                     "created_at": u.created_at} for u in sorted(proj.updates, key=lambda row: row.created_at, reverse=True)],
    }


@router.post("/{project_id}/updates", status_code=status.HTTP_201_CREATED)
async def create_project_update(project_id: uuid.UUID, req: CreateProjectUpdateSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        row = await project_service.record_project_update(db, tenant_id, project_id, **req.model_dump())
        return {"update_id": row.update_id, "project_id": row.project_id, "progress_pct": row.progress_pct,
                "notes": row.notes, "blockers": row.blockers, "created_at": row.created_at}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{project_id}/tasks", status_code=status.HTTP_201_CREATED, summary="Create Task for Project")
async def create_task(project_id: uuid.UUID, req: CreateTaskSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    task = await project_service.create_task(
        session=db,
        tenant_id=tenant_id,
        project_id=project_id,
        task_title=req.task_title,
        task_description=req.task_description,
        priority=req.priority,
        estimated_hours=req.estimated_hours,
        assigned_to_id=req.assigned_to_id,
        assigned_to_name=req.assigned_to_name,
        start_date=req.start_date,
        due_date=req.due_date,
    )
    return {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "task_title": task.task_title,
        "status": task.status,
    }


@router.patch("/tasks/{task_id}", summary="Update Project Task Status and Actual Hours")
async def update_task(task_id: uuid.UUID, req: UpdateTaskSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        t = await project_service.update_task(
            session=db,
            tenant_id=tenant_id,
            task_id=task_id,
            status=req.status,
            actual_hours=req.actual_hours,
        )
        return {"task_id": t.task_id, "status": t.status, "actual_hours": float(t.actual_hours)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/timesheets", status_code=status.HTTP_201_CREATED, summary="Log Timesheet Activity")
async def log_timesheet(project_id: uuid.UUID, req: CreateTimesheetSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    ts = await project_service.log_timesheet(
        session=db,
        tenant_id=tenant_id,
        timesheet_number=req.timesheet_number,
        employee_id=req.employee_id,
        project_id=project_id,
        hours=req.hours,
        billing_rate=req.billing_rate,
        costing_rate=req.costing_rate,
        task_id=req.task_id,
        employee_name=req.employee_name,
        activity_type=req.activity_type,
        work_date=req.work_date,
        is_billable=req.is_billable,
        notes=req.notes,
        activity_type_id=req.activity_type_id,
    )
    return {
        "timesheet_id": ts.timesheet_id,
        "timesheet_number": ts.timesheet_number,
        "hours": float(ts.hours),
        "costing_amount": float(ts.costing_amount),
        "billing_amount": float(ts.billing_amount),
    }



