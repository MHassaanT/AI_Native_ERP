"""Domain Service for CRM Leads and AI Qualification Scoring."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.crm import Lead, Opportunity
from erp.db.models.sales import Customer


class LeadService:
    """Enterprise lead acquisition, scoring, and conversion management."""

    def calculate_qualification_score(
        self,
        annual_revenue: Decimal,
        no_of_employees: int,
        has_email: bool,
        has_phone: bool,
        industry: str | None = None,
        source: str = "WEBSITE",
    ) -> tuple[Decimal, str]:
        """Calculates 0-100 qualification score and status tier."""
        score = Decimal("0.00")

        # Revenue dimension (max 40 pts)
        if annual_revenue >= Decimal("1000000.00"):
            score += Decimal("40.00")
        elif annual_revenue >= Decimal("250000.00"):
            score += Decimal("25.00")
        elif annual_revenue >= Decimal("50000.00"):
            score += Decimal("15.00")
        elif annual_revenue > Decimal("0.00"):
            score += Decimal("5.00")

        # Size dimension (max 25 pts)
        if no_of_employees >= 50:
            score += Decimal("25.00")
        elif no_of_employees >= 10:
            score += Decimal("15.00")
        elif no_of_employees >= 2:
            score += Decimal("10.00")
        else:
            score += Decimal("5.00")

        # Profile completeness dimension (max 25 pts)
        if has_email:
            score += Decimal("15.00")
        if has_phone:
            score += Decimal("10.00")

        # Industry & Source quality (max 10 pts)
        if industry and industry.strip():
            score += Decimal("5.00")
        if source in ["REFERRAL", "CAMPAIGN", "WALK_IN"]:
            score += Decimal("5.00")

        score = min(Decimal("100.00"), max(Decimal("0.00"), score))

        if score >= Decimal("60.00"):
            status = "QUALIFIED"
        elif score >= Decimal("30.00"):
            status = "IN_PROCESS"
        else:
            status = "UNQUALIFIED"

        return score, status

    async def create_lead(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lead_name: str,
        email_id: str | None = None,
        mobile_no: str | None = None,
        phone: str | None = None,
        company_name: str | None = None,
        annual_revenue: Decimal = Decimal("0.0000"),
        no_of_employees: int = 1,
        industry: str | None = None,
        market_segment: str | None = None,
        territory: str | None = None,
        source: str = "WEBSITE",
        status: str = "LEAD",
        lead_owner_id: uuid.UUID | None = None,
        notes: str | None = None,
        salutation: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> Lead:
        """Registers a new Lead and evaluates qualification score."""
        score, qual_status = self.calculate_qualification_score(
            annual_revenue=annual_revenue,
            no_of_employees=no_of_employees,
            has_email=bool(email_id and email_id.strip()),
            has_phone=bool((mobile_no and mobile_no.strip()) or (phone and phone.strip())),
            industry=industry,
            source=source,
        )

        lead = Lead(
            tenant_id=tenant_id,
            lead_name=lead_name.strip(),
            salutation=salutation,
            first_name=first_name,
            last_name=last_name,
            email_id=email_id.strip() if email_id else None,
            mobile_no=mobile_no.strip() if mobile_no else None,
            phone=phone.strip() if phone else None,
            company_name=company_name.strip() if company_name else None,
            annual_revenue=annual_revenue,
            no_of_employees=no_of_employees,
            industry=industry.strip() if industry else None,
            market_segment=market_segment.strip() if market_segment else None,
            territory=territory.strip() if territory else None,
            source=source.strip().upper(),
            status=status.strip().upper(),
            lead_owner_id=lead_owner_id,
            qualification_status=qual_status,
            qualification_score=score,
            notes=notes,
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return lead

    async def get_lead(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> Lead | None:
        """Retrieves a single lead by ID."""
        stmt = (
            select(Lead)
            .options(selectinload(Lead.customer))
            .where(Lead.tenant_id == tenant_id, Lead.lead_id == lead_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_leads(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Lead]:
        """Lists leads with status filtering and text search."""
        stmt = select(Lead).options(selectinload(Lead.customer)).where(Lead.tenant_id == tenant_id)

        if status:
            stmt = stmt.where(Lead.status == status.strip().upper())
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Lead.lead_name.ilike(term),
                    Lead.company_name.ilike(term),
                    Lead.email_id.ilike(term),
                )
            )

        stmt = stmt.order_by(Lead.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def convert_lead_to_opportunity(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        title: str | None = None,
        opportunity_amount: Decimal = Decimal("10000.0000"),
        sales_stage: str = "QUALIFICATION",
    ) -> Opportunity:
        """Converts an existing Lead into an active Opportunity pipeline deal."""
        lead = await self.get_lead(session, tenant_id, lead_id)
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        # Generate unique Opportunity Number
        count_stmt = select(func.count(Opportunity.opportunity_id)).where(
            Opportunity.tenant_id == tenant_id
        )
        total_opps = (await session.execute(count_stmt)).scalar() or 0
        opp_number = f"OPP-{total_opps + 1:04d}"

        deal_title = title or f"Deal with {lead.company_name or lead.lead_name}"
        opp = Opportunity(
            tenant_id=tenant_id,
            opportunity_number=opp_number,
            opportunity_from="LEAD",
            party_id=lead.lead_id,
            party_name=lead.company_name or lead.lead_name,
            title=deal_title,
            opportunity_type="SALES",
            opportunity_owner_id=lead.lead_owner_id,
            sales_stage=sales_stage.strip().upper(),
            probability=Decimal("25.00"),
            opportunity_amount=opportunity_amount,
            total_amount=opportunity_amount,
            notes=lead.notes,
        )
        session.add(opp)

        lead.status = "CONVERTED"
        lead.qualification_status = "QUALIFIED"
        await session.commit()
        await session.refresh(opp)
        return opp

    async def convert_lead_to_customer(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> Customer:
        """Converts an existing Lead into an active customer account in the ledger/commercial master."""
        lead = await self.get_lead(session, tenant_id, lead_id)
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        if lead.customer_id:
            existing_cust = (
                await session.execute(
                    select(Customer).where(
                        Customer.tenant_id == tenant_id,
                        Customer.customer_id == lead.customer_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_cust:
                return existing_cust

        # Create new Customer profile
        cust_code = f"CUST-{lead.lead_id.hex[:6].upper()}"
        cust_name = lead.company_name or lead.lead_name

        customer = Customer(
            tenant_id=tenant_id,
            customer_code=cust_code,
            customer_name=cust_name,
            email=lead.email_id,
            credit_limit=Decimal("15000.0000"),
            is_active=True,
        )
        session.add(customer)
        await session.flush()

        lead.customer_id = customer.customer_id
        lead.status = "CONVERTED"
        lead.qualification_status = "QUALIFIED"
        await session.commit()
        await session.refresh(customer)
        return customer


lead_service = LeadService()
