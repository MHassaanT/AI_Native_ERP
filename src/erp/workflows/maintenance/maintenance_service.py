"""Domain Service for Preventive Maintenance Schedules & Dispatched Visits."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dateutil.relativedelta import relativedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.assets import Asset
from erp.db.models.maintenance import MaintenanceSchedule, MaintenanceVisit


class MaintenanceService:
    """Enterprise Preventive Maintenance scheduling, technician visit tracking & machine uptime."""

    def compute_next_due_date(self, current_date: date, periodicity: str) -> date:
        p = periodicity.upper()
        if p == "WEEKLY":
            return current_date + relativedelta(weeks=1)
        elif p == "MONTHLY":
            return current_date + relativedelta(months=1)
        elif p == "QUARTERLY":
            return current_date + relativedelta(months=3)
        elif p == "ANNUAL":
            return current_date + relativedelta(years=1)
        return current_date + relativedelta(months=1)

    async def create_schedule(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_number: str,
        periodicity: str,
        start_date: date,
        task_description: str,
        asset_id: Optional[uuid.UUID] = None,
        item_code: Optional[str] = None,
        end_date: Optional[date] = None,
        checklist_items: Optional[List[str]] = None,
    ) -> MaintenanceSchedule:
        next_due = self.compute_next_due_date(start_date, periodicity)
        sched_id = uuid.uuid4()
        schedule = MaintenanceSchedule(
            schedule_id=sched_id,
            tenant_id=tenant_id,
            schedule_number=schedule_number,
            asset_id=asset_id,
            item_code=item_code,
            periodicity=periodicity.upper(),
            start_date=start_date,
            end_date=end_date,
            task_description=task_description,
            checklist_items=checklist_items or [],
            next_due_date=next_due,
            status="ACTIVE",
        )
        session.add(schedule)
        await session.flush()
        return schedule

    async def list_schedules(
        self, session: AsyncSession, tenant_id: uuid.UUID, status: Optional[str] = None
    ) -> List[MaintenanceSchedule]:
        stmt = (
            select(MaintenanceSchedule)
            .options(selectinload(MaintenanceSchedule.visits))
            .where(MaintenanceSchedule.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(MaintenanceSchedule.status == status.upper())
        stmt = stmt.order_by(MaintenanceSchedule.next_due_date)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_schedule(
        self, session: AsyncSession, tenant_id: uuid.UUID, schedule_id: uuid.UUID
    ) -> Optional[MaintenanceSchedule]:
        stmt = (
            select(MaintenanceSchedule)
            .options(selectinload(MaintenanceSchedule.visits))
            .execution_options(populate_existing=True)
            .where(
                MaintenanceSchedule.tenant_id == tenant_id,
                MaintenanceSchedule.schedule_id == schedule_id,
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def record_visit(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        visit_number: str,
        tasks_performed: str,
        schedule_id: Optional[uuid.UUID] = None,
        asset_id: Optional[uuid.UUID] = None,
        technician_id: Optional[uuid.UUID] = None,
        technician_name: Optional[str] = None,
        visit_date: Optional[date] = None,
        maintenance_type: str = "PREVENTIVE",
        parts_replaced: Optional[str] = None,
        downtime_hours: Decimal = Decimal("0.00"),
        maintenance_cost: Decimal = Decimal("0.0000"),
        status: str = "COMPLETED",
    ) -> MaintenanceVisit:
        v_date = visit_date or date.today()
        v_id = uuid.uuid4()
        visit = MaintenanceVisit(
            visit_id=v_id,
            tenant_id=tenant_id,
            visit_number=visit_number,
            schedule_id=schedule_id,
            asset_id=asset_id,
            technician_id=technician_id,
            technician_name=technician_name,
            visit_date=v_date,
            maintenance_type=maintenance_type.upper(),
            tasks_performed=tasks_performed,
            parts_replaced=parts_replaced,
            downtime_hours=downtime_hours,
            maintenance_cost=maintenance_cost,
            status=status.upper(),
        )
        session.add(visit)
        await session.flush()

        if schedule_id and status.upper() == "COMPLETED":
            from sqlalchemy import select
            stmt = (
                select(MaintenanceSchedule)
                .execution_options(populate_existing=True)
                .where(
                    MaintenanceSchedule.tenant_id == tenant_id,
                    MaintenanceSchedule.schedule_id == schedule_id,
                )
            )
            res = await session.execute(stmt)
            sched = res.scalar_one_or_none()
            if sched and sched.status == "ACTIVE":
                sched.next_due_date = self.compute_next_due_date(v_date, sched.periodicity)
                await session.flush()

        return visit

    async def list_visits(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
    ) -> List[MaintenanceVisit]:
        stmt = select(MaintenanceVisit).where(MaintenanceVisit.tenant_id == tenant_id)
        if asset_id:
            stmt = stmt.where(MaintenanceVisit.asset_id == asset_id)
        if status:
            stmt = stmt.where(MaintenanceVisit.status == status.upper())
        stmt = stmt.order_by(MaintenanceVisit.visit_date.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())


maintenance_service = MaintenanceService()
