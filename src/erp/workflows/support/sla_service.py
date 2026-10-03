"""Domain Service for Service Level Agreements (SLA) & Priority Rules."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.support import ServiceLevelAgreement, ServiceLevelPriority

DEFAULT_PRIORITIES = [
    {"priority": "URGENT", "response_time_hours": Decimal("1.00"), "resolution_time_hours": Decimal("4.00")},
    {"priority": "HIGH", "response_time_hours": Decimal("2.00"), "resolution_time_hours": Decimal("8.00")},
    {"priority": "MEDIUM", "response_time_hours": Decimal("4.00"), "resolution_time_hours": Decimal("24.00")},
    {"priority": "LOW", "response_time_hours": Decimal("8.00"), "resolution_time_hours": Decimal("48.00")},
]


class SlaService:
    """Enterprise SLA rules engine and deadline computation."""

    async def create_sla(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sla_name: str,
        is_default: bool = False,
        entity_type: str = "ALL",
        entity_id: uuid.UUID | None = None,
        priorities: list[dict[str, Any]] | None = None,
    ) -> ServiceLevelAgreement:
        """Configures an SLA with priority matrices."""
        sla_priorities = []
        p_list = priorities if priorities else DEFAULT_PRIORITIES
        for p in p_list:
            sla_priorities.append(
                ServiceLevelPriority(
                    tenant_id=tenant_id,
                    priority=str(p["priority"]).upper(),
                    response_time_hours=Decimal(str(p.get("response_time_hours", "4.0"))),
                    resolution_time_hours=Decimal(str(p.get("resolution_time_hours", "24.0"))),
                )
            )

        # If this is marked default, unset other defaults
        if is_default:
            existing = await self.list_slas(session, tenant_id)
            for ex in existing:
                if ex.is_default:
                    ex.is_default = False

        sla = ServiceLevelAgreement(
            tenant_id=tenant_id,
            sla_name=sla_name.strip(),
            document_type="ISSUE",
            is_default=is_default,
            entity_type=entity_type.strip().upper(),
            entity_id=entity_id,
            is_active=True,
            priorities=sla_priorities,
        )
        session.add(sla)
        await session.commit()
        return await self.get_sla(session, tenant_id, sla.sla_id)  # type: ignore

    async def get_sla(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sla_id: uuid.UUID,
    ) -> ServiceLevelAgreement | None:
        """Retrieves an SLA with priority schedules."""
        stmt = (
            select(ServiceLevelAgreement)
            .options(selectinload(ServiceLevelAgreement.priorities))
            .where(ServiceLevelAgreement.tenant_id == tenant_id, ServiceLevelAgreement.sla_id == sla_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_slas(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[ServiceLevelAgreement]:
        """Lists configured SLAs with priority schedules."""
        stmt = (
            select(ServiceLevelAgreement)
            .options(selectinload(ServiceLevelAgreement.priorities))
            .where(ServiceLevelAgreement.tenant_id == tenant_id)
            .order_by(ServiceLevelAgreement.is_default.desc(), ServiceLevelAgreement.created_at.desc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def get_or_create_default_sla(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
    ) -> ServiceLevelAgreement:
        """Finds matching customer SLA, global default SLA, or creates Standard SLA."""
        slas = await self.list_slas(session, tenant_id)

        # 1. Customer specific SLA
        if customer_id:
            for s in slas:
                if s.entity_type == "CUSTOMER" and s.entity_id == customer_id and s.is_active:
                    return s

        # 2. Global Default SLA
        for s in slas:
            if s.is_default and s.is_active:
                return s

        # 3. Any active SLA
        if slas:
            return slas[0]

        # 4. Bootstrap default Standard SLA
        return await self.create_sla(
            session=session,
            tenant_id=tenant_id,
            sla_name="Standard Support SLA",
            is_default=True,
            entity_type="ALL",
        )

    def calculate_deadlines(
        self,
        sla: ServiceLevelAgreement,
        priority: str,
        start_time: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """Calculates response_by and resolution_by timestamps according to SLA rules."""
        base_time = start_time or datetime.now(timezone.utc)
        p_norm = priority.strip().upper()

        resp_hours = Decimal("4.00")
        resol_hours = Decimal("24.00")

        if sla and sla.priorities:
            for p in sla.priorities:
                if p.priority.upper() == p_norm:
                    resp_hours = p.response_time_hours
                    resol_hours = p.resolution_time_hours
                    break

        response_by = base_time + timedelta(hours=float(resp_hours))
        resolution_by = base_time + timedelta(hours=float(resol_hours))
        return response_by, resolution_by


sla_service = SlaService()
