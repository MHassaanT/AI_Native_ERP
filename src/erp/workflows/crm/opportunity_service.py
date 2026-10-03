"""Domain Service for CRM Opportunities and Visual Pipeline Forecasting."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.crm import Opportunity, OpportunityItem, Lead
from erp.db.models.sales import Customer, SalesQuotation, SalesOrderItem

STAGE_PROBABILITIES = {
    "PROSPECTING": Decimal("10.00"),
    "QUALIFICATION": Decimal("25.00"),
    "PROPOSAL": Decimal("50.00"),
    "NEGOTIATION": Decimal("75.00"),
    "CLOSED_WON": Decimal("100.00"),
    "CLOSED_LOST": Decimal("0.00"),
}


class OpportunityService:
    """Enterprise deal progression and sales forecast management."""

    async def create_opportunity(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opportunity_number: str,
        party_id: uuid.UUID,
        party_name: str,
        title: str,
        opportunity_from: str = "LEAD",
        opportunity_type: str = "SALES",
        sales_stage: str = "PROSPECTING",
        probability: Decimal | None = None,
        opportunity_amount: Decimal = Decimal("0.0000"),
        expected_closing_date: date | None = None,
        notes: str | None = None,
        opportunity_owner_id: uuid.UUID | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> Opportunity:
        """Creates an Opportunity deal with optional line items."""
        stage_norm = sales_stage.strip().upper()
        prob = probability if probability is not None else STAGE_PROBABILITIES.get(stage_norm, Decimal("10.00"))

        calc_total = Decimal("0.0000")
        opp_items = []
        if items:
            for it in items:
                qty = Decimal(str(it.get("quantity", "1.0")))
                rate = Decimal(str(it.get("rate", "0.0")))
                amt = qty * rate
                calc_total += amt
                opp_items.append(
                    OpportunityItem(
                        tenant_id=tenant_id,
                        item_id=uuid.UUID(str(it["item_id"])),
                        item_code=str(it.get("item_code", "N/A")),
                        item_name=str(it.get("item_name", "Item")),
                        quantity=qty,
                        rate=rate,
                        amount=amt,
                    )
                )

        final_amount = calc_total if calc_total > Decimal("0.0000") else opportunity_amount

        opp = Opportunity(
            tenant_id=tenant_id,
            opportunity_number=opportunity_number.strip().upper(),
            opportunity_from=opportunity_from.strip().upper(),
            party_id=party_id,
            party_name=party_name.strip(),
            title=title.strip(),
            opportunity_type=opportunity_type.strip().upper(),
            opportunity_owner_id=opportunity_owner_id,
            sales_stage=stage_norm,
            probability=prob,
            expected_closing_date=expected_closing_date or (date.today() + timedelta(days=30)),
            opportunity_amount=final_amount,
            total_amount=final_amount,
            notes=notes,
            items=opp_items,
        )
        session.add(opp)
        await session.commit()
        return await self.get_opportunity(session, tenant_id, opp.opportunity_id)  # type: ignore

    async def get_opportunity(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opportunity_id: uuid.UUID,
    ) -> Opportunity | None:
        """Retrieves an opportunity with line items."""
        stmt = (
            select(Opportunity)
            .options(selectinload(Opportunity.items))
            .where(Opportunity.tenant_id == tenant_id, Opportunity.opportunity_id == opportunity_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_opportunities(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sales_stage: str | None = None,
        search: str | None = None,
    ) -> list[Opportunity]:
        """Lists opportunities with optional stage filter and search."""
        stmt = (
            select(Opportunity)
            .options(selectinload(Opportunity.items))
            .where(Opportunity.tenant_id == tenant_id)
        )

        if sales_stage:
            stmt = stmt.where(Opportunity.sales_stage == sales_stage.strip().upper())
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Opportunity.opportunity_number.ilike(term),
                    Opportunity.title.ilike(term),
                    Opportunity.party_name.ilike(term),
                )
            )

        stmt = stmt.order_by(Opportunity.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def update_stage(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opportunity_id: uuid.UUID,
        new_stage: str,
        lost_reason: str | None = None,
    ) -> Opportunity:
        """Transitions an opportunity stage and updates win probability."""
        opp = await self.get_opportunity(session, tenant_id, opportunity_id)
        if not opp:
            raise ValueError(f"Opportunity '{opportunity_id}' not found.")

        stage_clean = new_stage.strip().upper()
        opp.sales_stage = stage_clean
        opp.probability = STAGE_PROBABILITIES.get(stage_clean, opp.probability)

        if stage_clean == "CLOSED_LOST":
            opp.order_lost_reason = lost_reason or "Unspecified"
        elif stage_clean == "CLOSED_WON":
            opp.order_lost_reason = None

        await session.commit()
        return await self.get_opportunity(session, tenant_id, opp.opportunity_id)  # type: ignore

    async def get_pipeline_summary(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Calculates real-time pipeline valuation, weighted forecasting, and stage breakdown."""
        stmt = select(Opportunity).where(Opportunity.tenant_id == tenant_id)
        opps = list((await session.execute(stmt)).scalars().all())

        total_opps = len(opps)
        total_value = sum((o.total_amount for o in opps), Decimal("0.0000"))
        weighted_value = sum(
            (o.total_amount * (o.probability / Decimal("100.00")) for o in opps),
            Decimal("0.0000"),
        )

        stages_count: dict[str, int] = {
            "PROSPECTING": 0,
            "QUALIFICATION": 0,
            "PROPOSAL": 0,
            "NEGOTIATION": 0,
            "CLOSED_WON": 0,
            "CLOSED_LOST": 0,
        }
        stages_value: dict[str, float] = {
            "PROSPECTING": 0.0,
            "QUALIFICATION": 0.0,
            "PROPOSAL": 0.0,
            "NEGOTIATION": 0.0,
            "CLOSED_WON": 0.0,
            "CLOSED_LOST": 0.0,
        }

        won_count = 0
        lost_count = 0

        for o in opps:
            st = o.sales_stage.upper()
            if st in stages_count:
                stages_count[st] += 1
                stages_value[st] += float(o.total_amount)
            if st == "CLOSED_WON":
                won_count += 1
            elif st == "CLOSED_LOST":
                lost_count += 1

        total_closed = won_count + lost_count
        win_rate = (won_count / total_closed * 100.0) if total_closed > 0 else 0.0

        return {
            "total_deals": total_opps,
            "total_pipeline_value": float(total_value),
            "weighted_forecast_value": float(weighted_value),
            "win_rate_percentage": round(win_rate, 2),
            "stages_count": stages_count,
            "stages_value": stages_value,
        }

    async def convert_opportunity_to_quotation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opportunity_id: uuid.UUID,
        valid_days: int = 30,
    ) -> SalesQuotation:
        """Converts an opportunity deal into an official Sales Quotation in the commercial module."""
        opp = await self.get_opportunity(session, tenant_id, opportunity_id)
        if not opp:
            raise ValueError(f"Opportunity '{opportunity_id}' not found.")

        # Determine Customer profile
        customer = None
        if opp.opportunity_from == "CUSTOMER":
            customer = (
                await session.execute(
                    select(Customer).where(
                        Customer.tenant_id == tenant_id,
                        Customer.customer_id == opp.party_id,
                    )
                )
            ).scalar_one_or_none()
        else:
            # Lead origin: check if lead already has a customer profile or create one
            lead = (
                await session.execute(
                    select(Lead).where(Lead.tenant_id == tenant_id, Lead.lead_id == opp.party_id)
                )
            ).scalar_one_or_none()
            if lead and lead.customer_id:
                customer = (
                    await session.execute(
                        select(Customer).where(
                            Customer.tenant_id == tenant_id,
                            Customer.customer_id == lead.customer_id,
                        )
                    )
                ).scalar_one_or_none()

            if not customer:
                # Auto-provision Customer for this deal
                cust_code = f"CUST-OPP-{opp.opportunity_id.hex[:6].upper()}"
                customer = Customer(
                    tenant_id=tenant_id,
                    customer_code=cust_code,
                    customer_name=opp.party_name,
                    credit_limit=Decimal("20000.0000"),
                    is_active=True,
                )
                session.add(customer)
                await session.flush()
                if lead:
                    lead.customer_id = customer.customer_id

        # Generate Quotation Number
        count_stmt = select(func.count(SalesQuotation.quotation_id)).where(
            SalesQuotation.tenant_id == tenant_id
        )
        total_quotes = (await session.execute(count_stmt)).scalar() or 0
        quote_number = f"SQ-{date.today().year}-{total_quotes + 1:04d}"

        subtotal = opp.total_amount
        tax = subtotal * Decimal("0.10")  # 10% standard commercial tax
        total = subtotal + tax

        quotation = SalesQuotation(
            tenant_id=tenant_id,
            quotation_number=quote_number,
            customer_id=customer.customer_id,
            quotation_date=date.today(),
            valid_until=date.today() + timedelta(days=valid_days),
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            contribution_margin_pct=Decimal("35.00"),
            status="DRAFT",
        )
        session.add(quotation)

        # Transition opportunity stage to PROPOSAL
        opp.sales_stage = "PROPOSAL"
        opp.probability = Decimal("50.00")

        await session.commit()
        await session.refresh(quotation)
        return quotation


opportunity_service = OpportunityService()
