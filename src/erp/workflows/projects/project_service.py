"""Domain Service for Projects, Tasks, and Timesheet Cost/Billing Aggregation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.projects import Project, ProjectTask, Timesheet


class ProjectService:
    """Enterprise Project Management tracking milestones, labor timesheets, and cost rollups."""

    async def create_project(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        project_code: str,
        project_name: str,
        customer_id: Optional[uuid.UUID] = None,
        customer_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        estimated_cost: Decimal = Decimal("0.0000"),
        notes: Optional[str] = None,
    ) -> Project:
        proj_id = uuid.uuid4()
        project = Project(
            project_id=proj_id,
            tenant_id=tenant_id,
            project_code=project_code,
            project_name=project_name,
            customer_id=customer_id,
            customer_name=customer_name,
            start_date=start_date or date.today(),
            end_date=end_date,
            estimated_cost=estimated_cost,
            actual_cost=Decimal("0.0000"),
            total_billed_amount=Decimal("0.0000"),
            percent_complete=Decimal("0.00"),
            status="IN_PROGRESS",
            notes=notes,
        )
        session.add(project)
        await session.flush()
        return await self.get_project(session, tenant_id, proj_id)  # type: ignore

    async def get_project(
        self, session: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> Optional[Project]:
        stmt = (
            select(Project)
            .options(
                selectinload(Project.tasks),
                selectinload(Project.timesheets),
            )
            .execution_options(populate_existing=True).where(Project.tenant_id == tenant_id, Project.project_id == project_id)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_projects(
        self, session: AsyncSession, tenant_id: uuid.UUID, status: Optional[str] = None
    ) -> List[Project]:
        stmt = (
            select(Project)
            .options(
                selectinload(Project.tasks),
                selectinload(Project.timesheets),
            )
            .where(Project.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(Project.status == status.upper())
        stmt = stmt.order_by(Project.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def recalculate_project(
        self, session: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> Project:
        project = await self.get_project(session, tenant_id, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        ts_stmt = select(
            func.coalesce(func.sum(Timesheet.costing_amount), Decimal("0.0000")),
            func.coalesce(func.sum(Timesheet.billing_amount), Decimal("0.0000")),
        ).where(Timesheet.tenant_id == tenant_id, Timesheet.project_id == project_id)
        ts_res = await session.execute(ts_stmt)
        actual_cost, billed_amount = ts_res.one()

        project.actual_cost = actual_cost
        project.total_billed_amount = billed_amount

        tasks = project.tasks
        if tasks:
            completed_count = sum(1 for t in tasks if t.status == "COMPLETED")
            project.percent_complete = (
                (Decimal(str(completed_count)) / Decimal(str(len(tasks)))) * Decimal("100.00")
            ).quantize(Decimal("0.01"))
            if project.percent_complete >= Decimal("100.00"):
                project.status = "COMPLETED"

        await session.flush()
        return project

    async def create_task(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        task_title: str,
        task_description: Optional[str] = None,
        priority: str = "MEDIUM",
        estimated_hours: Decimal = Decimal("0.00"),
        assigned_to_id: Optional[uuid.UUID] = None,
        assigned_to_name: Optional[str] = None,
        start_date: Optional[date] = None,
        due_date: Optional[date] = None,
    ) -> ProjectTask:
        task_id = uuid.uuid4()
        task = ProjectTask(
            task_id=task_id,
            tenant_id=tenant_id,
            project_id=project_id,
            task_title=task_title,
            task_description=task_description,
            priority=priority.upper(),
            status="OPEN",
            start_date=start_date,
            due_date=due_date,
            estimated_hours=estimated_hours,
            actual_hours=Decimal("0.00"),
            assigned_to_id=assigned_to_id,
            assigned_to_name=assigned_to_name,
        )
        session.add(task)
        await session.flush()
        await self.recalculate_project(session, tenant_id, project_id)
        return task

    async def update_task(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        task_id: uuid.UUID,
        status: Optional[str] = None,
        actual_hours: Optional[Decimal] = None,
    ) -> ProjectTask:
        stmt = select(ProjectTask).where(
            ProjectTask.tenant_id == tenant_id, ProjectTask.task_id == task_id
        )
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found.")

        if status:
            task.status = status.upper()
        if actual_hours is not None:
            task.actual_hours = actual_hours

        await session.flush()
        await self.recalculate_project(session, tenant_id, task.project_id)
        return task

    async def log_timesheet(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        timesheet_number: str,
        employee_id: uuid.UUID,
        project_id: uuid.UUID,
        hours: Decimal,
        billing_rate: Decimal,
        costing_rate: Decimal,
        task_id: Optional[uuid.UUID] = None,
        employee_name: Optional[str] = None,
        activity_type: str = "ENGINEERING",
        work_date: Optional[date] = None,
        is_billable: bool = True,
        notes: Optional[str] = None,
    ) -> Timesheet:
        billing_amount = (hours * billing_rate).quantize(Decimal("0.0001"))
        costing_amount = (hours * costing_rate).quantize(Decimal("0.0001"))

        ts_id = uuid.uuid4()
        timesheet = Timesheet(
            timesheet_id=ts_id,
            tenant_id=tenant_id,
            timesheet_number=timesheet_number,
            employee_id=employee_id,
            employee_name=employee_name,
            project_id=project_id,
            task_id=task_id,
            activity_type=activity_type.upper(),
            work_date=work_date or date.today(),
            hours=hours,
            billing_rate=billing_rate,
            costing_rate=costing_rate,
            billing_amount=billing_amount,
            costing_amount=costing_amount,
            is_billable=is_billable,
            status="SUBMITTED",
            notes=notes,
        )
        session.add(timesheet)

        if task_id:
            stmt = select(ProjectTask).where(
                ProjectTask.tenant_id == tenant_id, ProjectTask.task_id == task_id
            )
            res = await session.execute(stmt)
            task = res.scalar_one_or_none()
            if task:
                task.actual_hours += hours

        await session.flush()
        await self.recalculate_project(session, tenant_id, project_id)
        return timesheet

    async def list_timesheets(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        employee_id: Optional[uuid.UUID] = None,
    ) -> List[Timesheet]:
        stmt = select(Timesheet).where(Timesheet.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(Timesheet.project_id == project_id)
        if employee_id:
            stmt = stmt.where(Timesheet.employee_id == employee_id)
        stmt = stmt.order_by(Timesheet.work_date.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())


project_service = ProjectService()
