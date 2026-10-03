"""Shop Floor MES Job Card Service: Punch clock timers, machine allocation, and scrap defect logging."""

from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.manufacturing import (
    BOM,
    BOMOperation,
    JobCard,
    JobCardTimeLog,
    WorkOrder,
    Workstation,
)

logger = logging.getLogger(__name__)


class JobCardService:
    """MES Shop Floor Job Card and Operator Punch Clock Execution Engine."""

    async def generate_job_cards_for_work_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order: WorkOrder,
        bom: BOM | None = None,
    ) -> list[JobCard]:
        """Creates sequenced Job Cards for each operational traveler step on the work order."""
        if not bom and work_order.bom_id:
            bom = (
                await session.execute(
                    select(BOM)
                    .options(selectinload(BOM.operations))
                    .where(BOM.tenant_id == tenant_id, BOM.bom_id == work_order.bom_id)
                )
            ).scalar_one_or_none()

        if not bom or not bom.operations:
            return []

        job_cards = []
        for op in bom.operations:
            jc_num = f"JC-{work_order.work_order_number}-{op.sequence_id:02d}"
            jc = JobCard(
                tenant_id=tenant_id,
                job_card_number=jc_num,
                work_order_id=work_order.work_order_id,
                operation_id=op.operation_id,
                workstation_id=op.workstation_id or work_order.workstation_id,
                sequence_id=op.sequence_id,
                for_quantity=work_order.planned_quantity,
                total_completed_qty=Decimal("0.0000"),
                total_scrap_qty=Decimal("0.0000"),
                total_time_in_mins=Decimal("0.0000"),
                status="PENDING",
            )
            session.add(jc)
            job_cards.append(jc)

        await session.flush()
        return job_cards

    async def get_job_card(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        job_card_id: uuid.UUID,
    ) -> JobCard | None:
        """Retrieves a Job Card with related operations, workstations, and time logs."""
        stmt = (
            select(JobCard)
            .options(
                selectinload(JobCard.operation),
                selectinload(JobCard.workstation),
                selectinload(JobCard.work_order),
                selectinload(JobCard.time_logs),
            )
            .where(JobCard.tenant_id == tenant_id, JobCard.job_card_id == job_card_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_job_cards(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order_id: uuid.UUID | None = None,
        workstation_id: uuid.UUID | None = None,
        employee_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[JobCard]:
        """Lists Job Cards with optional filtering."""
        stmt = (
            select(JobCard)
            .options(
                selectinload(JobCard.operation),
                selectinload(JobCard.workstation),
                selectinload(JobCard.work_order),
                selectinload(JobCard.time_logs),
            )
            .where(JobCard.tenant_id == tenant_id)
        )
        if work_order_id:
            stmt = stmt.where(JobCard.work_order_id == work_order_id)
        if workstation_id:
            stmt = stmt.where(JobCard.workstation_id == workstation_id)
        if employee_id:
            stmt = stmt.where(JobCard.employee_id == employee_id)
        if status:
            stmt = stmt.where(JobCard.status == status.upper())

        stmt = stmt.order_by(JobCard.sequence_id.asc(), JobCard.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def start_job_card(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        job_card_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
    ) -> JobCard:
        """Punches IN on a Job Card and starts the execution timer."""
        jc = await self.get_job_card(session, tenant_id, job_card_id)
        if not jc:
            raise ValueError(f"Job Card '{job_card_id}' not found.")

        if jc.status == "COMPLETED":
            raise ValueError("Job Card is already completed.")

        now_utc = datetime.now(UTC)
        jc.status = "WORK_IN_PROGRESS"
        jc.current_timer_started_at = now_utc
        if not jc.started_time:
            jc.started_time = now_utc
        if employee_id:
            jc.employee_id = employee_id

        # Update workstation status to IN_USE
        if jc.workstation_id:
            ws = (
                await session.execute(
                    select(Workstation).where(
                        Workstation.tenant_id == tenant_id,
                        Workstation.workstation_id == jc.workstation_id,
                    )
                )
            ).scalar_one_or_none()
            if ws and ws.status == "FAULT":
                raise ValueError(f"Cannot start Job Card: Workstation '{ws.workstation_code}' has an active FAULT lockout.")
            if ws:
                ws.status = "IN_USE"

        # Update parent work order to IN_PROCESS
        if jc.work_order and jc.work_order.status in ("DRAFT", "SCHEDULED"):
            jc.work_order.status = "IN_PROCESS"
            if not jc.work_order.actual_start_time:
                jc.work_order.actual_start_time = now_utc

        await session.flush()
        return jc

    async def pause_job_card(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        job_card_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        completed_qty: Decimal = Decimal("0.0000"),
        scrap_qty: Decimal = Decimal("0.0000"),
    ) -> JobCard:
        """Punches OUT or pauses current timer session, recording elapsed punch log."""
        jc = await self.get_job_card(session, tenant_id, job_card_id)
        if not jc:
            raise ValueError(f"Job Card '{job_card_id}' not found.")

        now_utc = datetime.now(UTC)
        elapsed_mins = Decimal("0.0000")

        if jc.current_timer_started_at:
            delta_seconds = (now_utc - jc.current_timer_started_at).total_seconds()
            elapsed_mins = Decimal(str(max(0.0, delta_seconds / 60.0)))

            time_log = JobCardTimeLog(
                tenant_id=tenant_id,
                job_card_id=jc.job_card_id,
                employee_id=employee_id or jc.employee_id,
                from_time=jc.current_timer_started_at,
                to_time=now_utc,
                time_in_mins=elapsed_mins,
                completed_qty=completed_qty,
                scrap_qty=scrap_qty,
            )
            session.add(time_log)

            jc.total_time_in_mins += elapsed_mins
            jc.current_timer_started_at = None

        jc.total_completed_qty += completed_qty
        jc.total_scrap_qty += scrap_qty
        jc.status = "PAUSED"

        # Release workstation
        if jc.workstation_id:
            ws = (
                await session.execute(
                    select(Workstation).where(
                        Workstation.tenant_id == tenant_id,
                        Workstation.workstation_id == jc.workstation_id,
                    )
                )
            ).scalar_one_or_none()
            if ws and ws.status == "IN_USE":
                ws.status = "OPERATIONAL"

        await session.flush()
        return jc

    async def complete_job_card(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        job_card_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        completed_qty: Decimal = Decimal("0.0000"),
        scrap_qty: Decimal = Decimal("0.0000"),
    ) -> JobCard:
        """Finishes the operation step, logging final cycle duration and releasing the workstation."""
        jc = await self.get_job_card(session, tenant_id, job_card_id)
        if not jc:
            raise ValueError(f"Job Card '{job_card_id}' not found.")

        now_utc = datetime.now(UTC)

        if jc.current_timer_started_at:
            delta_seconds = (now_utc - jc.current_timer_started_at).total_seconds()
            elapsed_mins = Decimal(str(max(0.0, delta_seconds / 60.0)))

            time_log = JobCardTimeLog(
                tenant_id=tenant_id,
                job_card_id=jc.job_card_id,
                employee_id=employee_id or jc.employee_id,
                from_time=jc.current_timer_started_at,
                to_time=now_utc,
                time_in_mins=elapsed_mins,
                completed_qty=completed_qty,
                scrap_qty=scrap_qty,
            )
            session.add(time_log)

            jc.total_time_in_mins += elapsed_mins
            jc.current_timer_started_at = None

        jc.total_completed_qty += completed_qty
        jc.total_scrap_qty += scrap_qty
        jc.status = "COMPLETED"

        # Release workstation
        if jc.workstation_id:
            ws = (
                await session.execute(
                    select(Workstation).where(
                        Workstation.tenant_id == tenant_id,
                        Workstation.workstation_id == jc.workstation_id,
                    )
                )
            ).scalar_one_or_none()
            if ws and ws.status == "IN_USE":
                ws.status = "OPERATIONAL"

        await session.flush()
        return jc


job_card_service = JobCardService()
