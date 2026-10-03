"""Domain Service for CRM Marketing Campaigns, Drip Sequences, Appointments, and Contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.crm import Appointment, Campaign, Contract, EmailCampaign


class CampaignService:
    """Enterprise marketing campaigns, drip emails, appointments, and service contracts."""

    async def create_campaign(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        campaign_name: str,
        campaign_type: str = "EMAIL",
        status: str = "ACTIVE",
        start_date: date | None = None,
        end_date: date | None = None,
        budget: Decimal = Decimal("0.0000"),
        actual_cost: Decimal = Decimal("0.0000"),
    ) -> Campaign:
        """Initializes a new marketing campaign."""
        camp = Campaign(
            tenant_id=tenant_id,
            campaign_name=campaign_name.strip(),
            campaign_type=campaign_type.strip().upper(),
            status=status.strip().upper(),
            start_date=start_date or date.today(),
            end_date=end_date,
            budget=budget,
            actual_cost=actual_cost,
        )
        session.add(camp)
        await session.commit()
        return await self.get_campaign(session, tenant_id, camp.campaign_id)  # type: ignore

    async def get_campaign(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> Campaign | None:
        """Retrieves a single campaign with drip steps."""
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.email_steps))
            .where(Campaign.tenant_id == tenant_id, Campaign.campaign_id == campaign_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_campaigns(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[Campaign]:
        """Lists marketing campaigns with optional status filtering."""
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.email_steps))
            .where(Campaign.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(Campaign.status == status.strip().upper())
        stmt = stmt.order_by(Campaign.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def add_drip_step(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
        sequence_step: int,
        delay_days: int,
        subject: str,
        template_body: str,
        lead_id: uuid.UUID | None = None,
    ) -> EmailCampaign:
        """Adds an automated email drip step to a campaign."""
        drip = EmailCampaign(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            lead_id=lead_id,
            sequence_step=sequence_step,
            delay_days=delay_days,
            subject=subject.strip(),
            template_body=template_body.strip(),
            status="PENDING",
        )
        session.add(drip)
        await session.commit()
        await session.refresh(drip)
        return drip

    async def list_campaign_drips(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> list[EmailCampaign]:
        """Lists all drip sequence steps for a campaign."""
        stmt = (
            select(EmailCampaign)
            .where(EmailCampaign.tenant_id == tenant_id, EmailCampaign.campaign_id == campaign_id)
            .order_by(EmailCampaign.sequence_step.asc())
        )
        return list((await session.execute(stmt)).scalars().all())

    # Appointments
    async def create_appointment(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        party_id: uuid.UUID,
        party_name: str,
        scheduled_time: datetime,
        appointment_with: str = "LEAD",
        duration_mins: int = 30,
        summary: str | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> Appointment:
        """Schedules a client/lead consultation appointment."""
        app = Appointment(
            tenant_id=tenant_id,
            appointment_with=appointment_with.strip().upper(),
            party_id=party_id,
            party_name=party_name.strip(),
            scheduled_time=scheduled_time,
            duration_mins=duration_mins,
            status="SCHEDULED",
            summary=summary,
            agent_id=agent_id,
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)
        return app

    async def list_appointments(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[Appointment]:
        """Lists calendar appointments."""
        stmt = select(Appointment).where(Appointment.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Appointment.status == status.strip().upper())
        stmt = stmt.order_by(Appointment.scheduled_time.asc())
        return list((await session.execute(stmt)).scalars().all())

    async def update_appointment_status(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
        status: str,
    ) -> Appointment:
        """Updates appointment status (SCHEDULED, CONFIRMED, COMPLETED, CANCELLED)."""
        stmt = select(Appointment).where(
            Appointment.tenant_id == tenant_id, Appointment.appointment_id == appointment_id
        )
        app = (await session.execute(stmt)).scalar_one_or_none()
        if not app:
            raise ValueError(f"Appointment '{appointment_id}' not found.")
        app.status = status.strip().upper()
        await session.commit()
        await session.refresh(app)
        return app

    # Contracts
    async def create_contract(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        contract_name: str,
        party_id: uuid.UUID,
        party_name: str,
        start_date: date,
        party_type: str = "CUSTOMER",
        end_date: date | None = None,
        contract_value: Decimal = Decimal("0.0000"),
        terms_and_conditions: str | None = None,
    ) -> Contract:
        """Registers a service agreement or commercial contract."""
        contract = Contract(
            tenant_id=tenant_id,
            contract_name=contract_name.strip(),
            party_type=party_type.strip().upper(),
            party_id=party_id,
            party_name=party_name.strip(),
            start_date=start_date,
            end_date=end_date,
            contract_value=contract_value,
            status="ACTIVE",
            terms_and_conditions=terms_and_conditions,
        )
        session.add(contract)
        await session.commit()
        await session.refresh(contract)
        return contract

    async def list_contracts(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[Contract]:
        """Lists active and past contracts."""
        stmt = select(Contract).where(Contract.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Contract.status == status.strip().upper())
        stmt = stmt.order_by(Contract.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


campaign_service = CampaignService()
