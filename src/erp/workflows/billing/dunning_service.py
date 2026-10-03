"""Dunning and Overdue Receivables Management Service.

Identifies overdue customer invoices, classifies into dunning tiers,
calculates late fees and statutory interest, and issues formal notices.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.billing import DunningNotice, DunningType
from erp.db.models.sales import SalesInvoice


class DunningService:
    """Overdue dunning engine."""

    async def create_dunning_type(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        dunning_type_name: str,
        overdue_days: int,
        fee_amount: Decimal,
        interest_rate_pct: Decimal,
        message_body: str,
    ) -> DunningType:
        """Registers a dunning severity level."""
        dtype = DunningType(
            tenant_id=tenant_id,
            dunning_type_name=dunning_type_name,
            overdue_days=overdue_days,
            fee_amount=fee_amount,
            interest_rate_pct=interest_rate_pct,
            message_body=message_body,
        )
        session.add(dtype)
        await session.flush()
        return dtype

    async def evaluate_overdue_invoices(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: date | None = None,
    ) -> list[dict]:
        """Scans unpaid invoices, matches against dunning levels, and creates Dunning Notices."""
        eval_date = as_of_date or date.today()

        # Fetch configured dunning types sorted by overdue days descending
        types_stmt = (
            select(DunningType)
            .where(DunningType.tenant_id == tenant_id)
            .order_by(DunningType.overdue_days.desc())
        )
        types_res = await session.execute(types_stmt)
        dunning_levels = types_res.scalars().all()

        if not dunning_levels:
            # Default Level 1 if none registered
            default_type = await self.create_dunning_type(
                session=session,
                tenant_id=tenant_id,
                dunning_type_name="First Reminder",
                overdue_days=15,
                fee_amount=Decimal("25.0000"),
                interest_rate_pct=Decimal("5.00"),
                message_body="Your invoice is overdue. Please remit payment immediately to avoid service interruption.",
            )
            dunning_levels = [default_type]

        # Query unpaid invoices past due date
        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.tenant_id == tenant_id,
            SalesInvoice.status == "ISSUED",
            SalesInvoice.due_date < eval_date,
        )
        inv_res = await session.execute(inv_stmt)
        overdue_invoices = inv_res.scalars().all()

        created_notices = []

        for inv in overdue_invoices:
            days_overdue = (eval_date - inv.due_date).days
            if days_overdue <= 0:
                continue

            # Match highest applicable dunning level
            applicable_level = None
            for lvl in dunning_levels:
                if days_overdue >= lvl.overdue_days:
                    applicable_level = lvl
                    break

            if not applicable_level:
                continue

            # Check if a notice was already issued for this level
            existing_stmt = select(DunningNotice).where(
                DunningNotice.tenant_id == tenant_id,
                DunningNotice.invoice_id == inv.invoice_id,
                DunningNotice.dunning_type_id == applicable_level.dunning_type_id,
            )
            existing_res = await session.execute(existing_stmt)
            if existing_res.scalars().first():
                continue

            # Compute interest: (outstanding * rate / 100) * (days_overdue / 365)
            outstanding = inv.total_amount
            interest = (outstanding * (applicable_level.interest_rate_pct / Decimal("100"))) * (
                Decimal(days_overdue) / Decimal("365")
            )
            interest = round(interest, 4)
            fee = applicable_level.fee_amount
            total_dunning = outstanding + fee + interest

            notice_num = f"DUN-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

            notice = DunningNotice(
                tenant_id=tenant_id,
                notice_number=notice_num,
                invoice_id=inv.invoice_id,
                customer_id=inv.customer_id,
                dunning_type_id=applicable_level.dunning_type_id,
                posting_date=eval_date,
                overdue_days=days_overdue,
                outstanding_amount=outstanding,
                fee_amount=fee,
                interest_amount=interest,
                total_dunning_amount=total_dunning,
                status="ISSUED",
            )
            session.add(notice)
            await session.flush()

            created_notices.append({
                "notice_id": str(notice.notice_id),
                "notice_number": notice_num,
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id),
                "overdue_days": days_overdue,
                "dunning_level": applicable_level.dunning_type_name,
                "fee_amount": float(fee),
                "interest_amount": float(interest),
                "total_dunning_amount": float(total_dunning),
            })

        return created_notices
