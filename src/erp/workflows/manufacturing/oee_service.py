"""OEE Telemetry and Machine Downtime Service (Overall Equipment Effectiveness)."""

from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.manufacturing import DowntimeEntry, JobCard, Workstation

logger = logging.getLogger(__name__)


class OEEService:
    """Computes Availability, Performance, Quality, and OEE KPIs for factory machines."""

    async def record_downtime(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        downtime_number: str,
        workstation_id: uuid.UUID,
        reason: str = "MECHANICAL_BREAKDOWN",
        fault_code: str | None = None,
        operator_id: uuid.UUID | None = None,
        notes: str | None = None,
        from_time: datetime | None = None,
    ) -> DowntimeEntry:
        """Records an unplanned stop or breakdown and locks the workstation."""
        from_dt = from_time or datetime.now(UTC)

        ws = (
            await session.execute(
                select(Workstation).where(
                    Workstation.tenant_id == tenant_id,
                    Workstation.workstation_id == workstation_id,
                )
            )
        ).scalar_one_or_none()
        if not ws:
            raise ValueError(f"Workstation '{workstation_id}' not found.")

        # Update workstation status and health
        ws.status = "FAULT" if "FAULT" in reason.upper() or "BREAKDOWN" in reason.upper() else "MAINTENANCE"
        ws.health_score = Decimal("35.00")

        downtime = DowntimeEntry(
            tenant_id=tenant_id,
            downtime_number=downtime_number.strip(),
            workstation_id=workstation_id,
            operator_id=operator_id,
            from_time=from_dt,
            reason=reason,
            fault_code=fault_code,
            notes=notes,
            status="OPEN",
            duration_mins=Decimal("0.0000"),
        )
        session.add(downtime)
        await session.flush()
        return downtime

    async def resolve_downtime(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        downtime_id: uuid.UUID,
        to_time: datetime | None = None,
    ) -> DowntimeEntry:
        """Resolves a machine stoppage, records duration, and restores workstation to OPERATIONAL."""
        stmt = select(DowntimeEntry).where(
            DowntimeEntry.tenant_id == tenant_id,
            DowntimeEntry.downtime_id == downtime_id,
        )
        downtime = (await session.execute(stmt)).scalar_one_or_none()
        if not downtime:
            raise ValueError(f"Downtime entry '{downtime_id}' not found.")

        to_dt = to_time or datetime.now(UTC)
        downtime.to_time = to_dt
        downtime.status = "RESOLVED"

        duration_sec = (to_dt - downtime.from_time).total_seconds()
        downtime.duration_mins = Decimal(str(max(0.0, duration_sec / 60.0)))

        # Restore workstation
        ws = (
            await session.execute(
                select(Workstation).where(
                    Workstation.tenant_id == tenant_id,
                    Workstation.workstation_id == downtime.workstation_id,
                )
            )
        ).scalar_one_or_none()
        if ws:
            ws.status = "OPERATIONAL"
            ws.health_score = Decimal("100.00")

        await session.flush()
        return downtime

    async def list_downtimes(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        workstation_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[DowntimeEntry]:
        """Lists machine downtime entries."""
        stmt = (
            select(DowntimeEntry)
            .where(DowntimeEntry.tenant_id == tenant_id)
        )
        if workstation_id:
            stmt = stmt.where(DowntimeEntry.workstation_id == workstation_id)
        if status:
            stmt = stmt.where(DowntimeEntry.status == status.upper())
        stmt = stmt.order_by(DowntimeEntry.from_time.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def calculate_workstation_oee(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        workstation_id: uuid.UUID,
        planned_production_minutes: float = 480.0,
    ) -> dict[str, Any]:
        """Calculates Availability, Performance, Quality, and composite OEE for a workstation."""
        ws = (
            await session.execute(
                select(Workstation).where(
                    Workstation.tenant_id == tenant_id,
                    Workstation.workstation_id == workstation_id,
                )
            )
        ).scalar_one_or_none()
        if not ws:
            raise ValueError(f"Workstation '{workstation_id}' not found.")

        # 1. Total Downtime
        dt_stmt = select(
            func.coalesce(func.sum(DowntimeEntry.duration_mins), Decimal("0.0000"))
        ).where(
            DowntimeEntry.tenant_id == tenant_id,
            DowntimeEntry.workstation_id == workstation_id,
        )
        downtime_mins = float((await session.execute(dt_stmt)).scalar() or 0.0)

        # 2. Operating Time & Availability
        operating_time = max(0.0, planned_production_minutes - downtime_mins)
        availability = operating_time / planned_production_minutes if planned_production_minutes > 0 else 1.0
        availability = max(0.0, min(1.0, availability))

        # 3. Production Count & Quality
        jc_stmt = select(
            func.coalesce(func.sum(JobCard.total_completed_qty), Decimal("0.0000")),
            func.coalesce(func.sum(JobCard.total_scrap_qty), Decimal("0.0000")),
        ).where(
            JobCard.tenant_id == tenant_id,
            JobCard.workstation_id == workstation_id,
        )
        jc_row = (await session.execute(jc_stmt)).one()
        total_produced = float(jc_row[0])
        total_scrap = float(jc_row[1])

        if total_produced > 0:
            good_count = max(0.0, total_produced - total_scrap)
            quality = good_count / total_produced
        else:
            quality = 1.0

        # 4. Performance
        # Ideal cycle time: standard 15 mins or derived from machine capacity
        cap = float(ws.production_capacity) if ws.production_capacity > Decimal("0") else 1.0
        ideal_cycle_mins = 60.0 / cap if cap > 0 else 15.0

        if operating_time > 0 and total_produced > 0:
            performance = (ideal_cycle_mins * total_produced) / operating_time
            performance = max(0.0, min(1.0, performance))
        else:
            performance = 1.0 if downtime_mins == 0 else 0.0

        oee = round(availability * performance * quality * 100.0, 2)

        return {
            "workstation_id": str(ws.workstation_id),
            "workstation_code": ws.workstation_code,
            "workstation_name": ws.workstation_name,
            "status": ws.status,
            "health_score": float(ws.health_score),
            "planned_production_minutes": planned_production_minutes,
            "downtime_minutes": round(downtime_mins, 2),
            "operating_time_minutes": round(operating_time, 2),
            "total_produced_qty": total_produced,
            "total_scrap_qty": total_scrap,
            "availability": round(availability, 4),
            "performance": round(performance, 4),
            "quality": round(quality, 4),
            "oee_percentage": oee,
        }


oee_service = OEEService()
