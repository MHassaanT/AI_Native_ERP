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
    billing_rate: Decimal = Decimal("100.0000")
    costing_rate: Decimal = Decimal("50.0000")
    task_id: Optional[uuid.UUID] = None
    employee_name: Optional[str] = None
    activity_type: str = "ENGINEERING"
    work_date: Optional[date] = None
    is_billable: bool = True
    notes: Optional[str] = None


# Endpoints
@router.post("", status_code=status.HTTP_201_CREATED, summary="Create Project")
async def create_project(req: CreateProjectSchema, tenant_id: TenantIdDep, db: DbSessionDep):
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
    )
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
    }


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
    )
    return {
        "timesheet_id": ts.timesheet_id,
        "timesheet_number": ts.timesheet_number,
        "hours": float(ts.hours),
        "costing_amount": float(ts.costing_amount),
        "billing_amount": float(ts.billing_amount),
    }



