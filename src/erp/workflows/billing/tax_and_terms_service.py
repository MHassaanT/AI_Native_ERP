"""Payment Terms Templates, Multi-Tier Taxes, and Advance Allocation Service.

Provides 1:1 ERPNext parity for:
- Payment Terms Templates & Invoice Payment Schedules
- Multi-tier cascading Sales Taxes & Charges Templates
- Customer Advance Payment Allocation against Sales Invoices
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.billing import (
    AdvancePaymentAllocation,
    PaymentSchedule,
    PaymentTermsTemplate,
    PaymentTermsTemplateDetail,
    SalesTaxesAndChargesTemplate,
    SalesTaxesAndChargesTemplateDetail,
)
from erp.db.models.sales import Customer, SalesInvoice


class TaxAndTermsService:
    """Core domain logic for Payment Terms, Tax Templates, and Advance Allocation."""

    # =========================================================================
    # 1. Payment Terms Templates & Schedules
    # =========================================================================

    async def create_payment_terms_template(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        template_name: str,
        terms: list[dict],  # [{"description": str, "invoice_portion": Decimal, "due_date_based_on": str, "credit_days": int}]
        allocate_payment_based_on_payment_terms: bool = True,
    ) -> PaymentTermsTemplate:
        """Creates a payment terms template with child terms."""
        total_portion = sum(Decimal(str(t["invoice_portion"])) for t in terms)
        if round(total_portion, 2) != Decimal("100.00"):
            raise ValueError(f"Total invoice portion across terms must equal 100.00%, got {total_portion}%")

        template = PaymentTermsTemplate(
            tenant_id=tenant_id,
            template_name=template_name,
            allocate_payment_based_on_payment_terms=allocate_payment_based_on_payment_terms,
            is_active=True,
        )
        session.add(template)
        await session.flush()

        for t in terms:
            detail = PaymentTermsTemplateDetail(
                tenant_id=tenant_id,
                template_id=template.template_id,
                description=t["description"],
                invoice_portion=Decimal(str(t["invoice_portion"])),
                due_date_based_on=t.get("due_date_based_on", "Day(s) after invoice date"),
                credit_days=int(t.get("credit_days", 0)),
            )
            session.add(detail)

        await session.flush()
        stmt = (
            select(PaymentTermsTemplate)
            .options(selectinload(PaymentTermsTemplate.terms))
            .where(PaymentTermsTemplate.template_id == template.template_id)
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def generate_payment_schedule_for_invoice(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> list[PaymentSchedule]:
        """Applies a payment terms template to a Sales Invoice, generating scheduled milestones."""
        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.invoice_id == invoice_id,
            SalesInvoice.tenant_id == tenant_id,
        )
        inv_res = await session.execute(inv_stmt)
        invoice = inv_res.scalars().first()
        if not invoice:
            raise ValueError(f"Sales Invoice {invoice_id} not found.")

        tmpl_stmt = (
            select(PaymentTermsTemplate)
            .options(selectinload(PaymentTermsTemplate.terms))
            .where(
                PaymentTermsTemplate.template_id == template_id,
                PaymentTermsTemplate.tenant_id == tenant_id,
            )
        )
        tmpl_res = await session.execute(tmpl_stmt)
        template = tmpl_res.scalars().first()
        if not template:
            raise ValueError(f"Payment Terms Template {template_id} not found.")

        # Delete any existing schedule lines
        existing_stmt = select(PaymentSchedule).where(PaymentSchedule.invoice_id == invoice_id)
        existing_res = await session.execute(existing_stmt)
        for ex in existing_res.scalars().all():
            await session.delete(ex)

        schedules: list[PaymentSchedule] = []
        posting_date = getattr(invoice, "invoice_date", None) or getattr(invoice, "posting_date", None) or date.today()
        grand_total = getattr(invoice, "grand_total", None) or getattr(invoice, "total_amount", Decimal("0.0000"))

        for term in template.terms:
            portion_pct = term.invoice_portion
            portion_amt = round(grand_total * (portion_pct / Decimal("100.00")), 4)

            # Compute due date based on credit_days
            due_date = posting_date + timedelta(days=term.credit_days)

            sched = PaymentSchedule(
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                payment_term=term.description,
                due_date=due_date,
                portion_pct=portion_pct,
                portion_amount=portion_amt,
                paid_amount=Decimal("0.0000"),
                outstanding_amount=portion_amt,
                status="UNPAID",
            )
            session.add(sched)
            schedules.append(sched)

        await session.flush()
        return schedules

    # =========================================================================
    # 2. Multi-Tier Sales Taxes & Charges Templates
    # =========================================================================

    async def create_tax_template(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        title: str,
        tax_category: str = "Standard",
        is_default: bool = False,
        taxes: list[dict] = None,  # [{"charge_type": str, "row_id": int|None, "account_head": str, "description": str, "rate": Decimal}]
    ) -> SalesTaxesAndChargesTemplate:
        """Creates a multi-tier taxes & charges template."""
        template = SalesTaxesAndChargesTemplate(
            tenant_id=tenant_id,
            title=title,
            tax_category=tax_category,
            is_default=is_default,
            disabled=False,
        )
        session.add(template)
        await session.flush()

        if taxes:
            for t in taxes:
                detail = SalesTaxesAndChargesTemplateDetail(
                    tenant_id=tenant_id,
                    template_id=template.template_id,
                    charge_type=t.get("charge_type", "On Net Total"),
                    row_id=t.get("row_id"),
                    account_head=t["account_head"],
                    description=t["description"],
                    rate=Decimal(str(t.get("rate", "0.0000"))),
                )
                session.add(detail)

        await session.flush()
        stmt = (
            select(SalesTaxesAndChargesTemplate)
            .options(selectinload(SalesTaxesAndChargesTemplate.taxes))
            .where(SalesTaxesAndChargesTemplate.template_id == template.template_id)
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    def calculate_taxes_and_charges(
        self,
        net_total: Decimal,
        tax_details: list[dict],
    ) -> dict[str, Any]:
        """Calculates multi-tier compounding taxes and charges matching ERPNext calculation engine.
        
        Supported charge types:
        - Actual: Fixed fee amount (e.g. $25 freight or handling)
        - On Net Total: Rate % applied to net_total
        - On Previous Row Amount: Rate % applied to the calculated tax/charge amount of reference row_id
        """
        row_calculations = []
        total_taxes = Decimal("0.0000")

        for idx, t in enumerate(tax_details, start=1):
            ctype = t.get("charge_type", "On Net Total")
            rate = Decimal(str(t.get("rate", "0.0000")))
            row_tax = Decimal("0.0000")

            if ctype == "Actual":
                row_tax = rate
            elif ctype == "On Net Total":
                row_tax = round(net_total * (rate / Decimal("100.00")), 4)
            elif ctype == "On Previous Row Amount":
                ref_row_id = t.get("row_id")
                # Find matching row by 1-based index or index-1
                ref_amount = Decimal("0.0000")
                if ref_row_id is not None and 1 <= int(ref_row_id) <= len(row_calculations):
                    ref_amount = row_calculations[int(ref_row_id) - 1]["tax_amount"]
                row_tax = round(ref_amount * (rate / Decimal("100.00")), 4)

            total_taxes += row_tax
            row_calculations.append({
                "row_id": idx,
                "account_head": t.get("account_head", "TAX"),
                "description": t.get("description", "Tax Head"),
                "charge_type": ctype,
                "rate": float(rate),
                "tax_amount": row_tax,
                "cumulative_total": net_total + total_taxes,
            })

        return {
            "net_total": float(net_total),
            "total_taxes_and_charges": float(total_taxes),
            "grand_total": float(net_total + total_taxes),
            "rows": [
                {**r, "tax_amount": float(r["tax_amount"]), "cumulative_total": float(r["cumulative_total"])}
                for r in row_calculations
            ],
        }

    # =========================================================================
    # 3. Customer Advance Payment Allocation
    # =========================================================================

    async def allocate_advance_payment(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        invoice_id: uuid.UUID,
        allocated_amount: Decimal,
        reference_note: str | None = None,
    ) -> AdvancePaymentAllocation:
        """Allocates advance payment towards an unpaid Sales Invoice, updating invoice outstanding balance."""
        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.invoice_id == invoice_id,
            SalesInvoice.tenant_id == tenant_id,
        )
        inv_res = await session.execute(inv_stmt)
        invoice = inv_res.scalars().first()
        if not invoice:
            raise ValueError(f"Sales Invoice {invoice_id} not found.")

        current_outstanding = getattr(invoice, "outstanding_amount", None)
        if current_outstanding is None:
            current_outstanding = getattr(invoice, "grand_total", None) or getattr(invoice, "total_amount", Decimal("0.0000"))

        if allocated_amount > current_outstanding:
            raise ValueError(f"Allocation amount ${allocated_amount} exceeds invoice outstanding balance ${current_outstanding}.")

        allocation = AdvancePaymentAllocation(
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            allocated_amount=allocated_amount,
            reference_note=reference_note or f"Advance reconciliation against {getattr(invoice, 'invoice_number', 'INV')}",
            posting_date=date.today(),
        )
        session.add(allocation)

        # Update invoice outstanding and status
        new_outstanding = current_outstanding - allocated_amount
        if hasattr(invoice, "outstanding_amount"):
            invoice.outstanding_amount = new_outstanding
        if new_outstanding == Decimal("0.0000"):
            invoice.status = "PAID"
        else:
            invoice.status = "PARTIAL"

        await session.flush()
        return allocation
