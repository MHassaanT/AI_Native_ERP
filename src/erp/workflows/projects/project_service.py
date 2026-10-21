"""Domain Service for Projects, Tasks, and Timesheet Cost/Billing Aggregation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.projects import ActivityCost, ActivityType, Project, ProjectTask, ProjectType, ProjectUpdate, Timesheet


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
        project_type_id: uuid.UUID | None = None,
    ) -> Project:
        if project_type_id:
            project_type = (await session.execute(select(ProjectType).where(
                ProjectType.tenant_id == tenant_id, ProjectType.project_type_id == project_type_id,
                ProjectType.is_active.is_(True),
            ))).scalar_one_or_none()
            if not project_type:
                raise ValueError("Project type not found or inactive.")
        proj_id = uuid.uuid4()
        project = Project(
            project_id=proj_id,
            tenant_id=tenant_id,
            project_code=project_code,
            project_name=project_name,
            project_type_id=project_type_id,
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
                selectinload(Project.updates),
                selectinload(Project.project_type),
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
                selectinload(Project.project_type),
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
            func.coalesce(func.sum(Timesheet.billing_amount).filter(Timesheet.is_billable.is_(True)), Decimal("0.0000")),
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
        billing_rate: Decimal | None,
        costing_rate: Decimal | None,
        task_id: Optional[uuid.UUID] = None,
        employee_name: Optional[str] = None,
        activity_type: str = "ENGINEERING",
        work_date: Optional[date] = None,
        is_billable: bool = True,
        notes: Optional[str] = None,
        activity_type_id: uuid.UUID | None = None,
    ) -> Timesheet:
        activity = None
        if activity_type_id:
            activity = (await session.execute(select(ActivityType).where(
                ActivityType.tenant_id == tenant_id, ActivityType.activity_type_id == activity_type_id,
                ActivityType.is_active.is_(True),
            ))).scalar_one_or_none()
            if not activity:
                raise ValueError("Activity type not found or inactive.")
            ref_date = work_date or date.today()
            cost_stmt = select(ActivityCost).where(
                ActivityCost.tenant_id == tenant_id, ActivityCost.activity_type_id == activity_type_id,
                ActivityCost.valid_from <= ref_date,
                (ActivityCost.valid_to.is_(None) | (ActivityCost.valid_to >= ref_date)),
                (ActivityCost.employee_id == employee_id) | (ActivityCost.employee_id.is_(None)),
            ).order_by(ActivityCost.employee_id.is_(None), ActivityCost.valid_from.desc())
            rate = (await session.execute(cost_stmt)).scalars().first()
            if rate:
                billing_rate = billing_rate if billing_rate is not None else rate.billing_rate
                costing_rate = costing_rate if costing_rate is not None else rate.costing_rate
            activity_type = activity.activity_name
        else:
            activity_type = activity_type
        billing_rate = billing_rate if billing_rate is not None else Decimal("100.0000")
        costing_rate = costing_rate if costing_rate is not None else Decimal("50.0000")
        if hours < 0:
            raise ValueError("Timesheet hours cannot be negative.")
        project = await self.get_project(session, tenant_id, project_id)
        if not project:
            raise ValueError("Project not found in this workspace.")
        billing_amount = (hours * billing_rate).quantize(Decimal("0.0001")) if is_billable else Decimal("0.0000")
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
            activity_type_id=activity_type_id,
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
            if not task or task.project_id != project_id:
                raise ValueError("Task must belong to the selected project and workspace.")
            task.actual_hours += hours

        await session.flush()
        await self.recalculate_project(session, tenant_id, project_id)
        return timesheet

    async def record_project_update(self, session: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID,
                                    sender_email: str, notes: str, progress_pct: int | None = None,
                                    blockers: str | None = None) -> ProjectUpdate:
        project = await self.get_project(session, tenant_id, project_id)
        if not project:
            raise ValueError("Project not found.")
        if progress_pct is not None and not 0 <= progress_pct <= 100:
            raise ValueError("Progress must be between 0 and 100.")
        if not sender_email.strip() or not notes.strip():
            raise ValueError("Sender email and update notes are required.")
        update = ProjectUpdate(tenant_id=tenant_id, project_id=project_id, sender_email=sender_email.strip(),
                               notes=notes.strip(), progress_pct=progress_pct, blockers=blockers.strip() if blockers else None)
        session.add(update)
        project.last_update_summary = notes.strip()
        if progress_pct is not None:
            project.percent_complete = Decimal(progress_pct).quantize(Decimal("0.01"))
            if progress_pct == 100:
                project.status = "COMPLETED"
            elif project.status == "COMPLETED":
                project.status = "IN_PROGRESS"
        await session.flush()
        return update

    async def create_project_type(self, session: AsyncSession, tenant_id: uuid.UUID, type_name: str, description: str | None = None) -> ProjectType:
        if not type_name.strip():
            raise ValueError("Project type name is required.")
        row = ProjectType(tenant_id=tenant_id, type_name=type_name.strip(), description=description, is_active=True)
        session.add(row)
        await session.flush()
        return row

    async def list_project_types(self, session: AsyncSession, tenant_id: uuid.UUID) -> list[ProjectType]:
        return list((await session.execute(select(ProjectType).where(ProjectType.tenant_id == tenant_id).order_by(ProjectType.type_name))).scalars().all())

    async def create_activity_type(self, session: AsyncSession, tenant_id: uuid.UUID, activity_name: str, description: str | None = None) -> ActivityType:
        if not activity_name.strip():
            raise ValueError("Activity type name is required.")
        row = ActivityType(tenant_id=tenant_id, activity_name=activity_name.strip(), description=description, is_active=True)
        session.add(row)
        await session.flush()
        return row

    async def list_activity_types(self, session: AsyncSession, tenant_id: uuid.UUID) -> list[ActivityType]:
        return list((await session.execute(select(ActivityType).where(ActivityType.tenant_id == tenant_id).order_by(ActivityType.activity_name))).scalars().all())

    async def create_activity_cost(self, session: AsyncSession, tenant_id: uuid.UUID, activity_type_id: uuid.UUID,
                                   billing_rate: Decimal, costing_rate: Decimal, valid_from: date,
                                   valid_to: date | None = None, employee_id: uuid.UUID | None = None) -> ActivityCost:
        if billing_rate < 0 or costing_rate < 0 or (valid_to and valid_to < valid_from):
            raise ValueError("Rates must be non-negative and the effective date range must be valid.")
        activity = (await session.execute(select(ActivityType).where(ActivityType.tenant_id == tenant_id, ActivityType.activity_type_id == activity_type_id))).scalar_one_or_none()
        if not activity:
            raise ValueError("Activity type not found.")
        row = ActivityCost(tenant_id=tenant_id, activity_type_id=activity_type_id, employee_id=employee_id,
                           billing_rate=billing_rate, costing_rate=costing_rate, valid_from=valid_from, valid_to=valid_to)
        session.add(row)
        await session.flush()
        return row

    async def list_activity_costs(self, session: AsyncSession, tenant_id: uuid.UUID) -> list[ActivityCost]:
        stmt = select(ActivityCost).options(selectinload(ActivityCost.activity_type)).where(ActivityCost.tenant_id == tenant_id).order_by(ActivityCost.valid_from.desc())
        return list((await session.execute(stmt)).scalars().all())

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
