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

from sqlalchemy import func, select
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
from erp.db.models.ledger import GeneralLedgerEntry
from erp.ledger.engine import LedgerEngine, TransactionProposal
from erp.ledger.invariants import LedgerLineProposal
from erp.ledger.locks import acquire_advisory_xact_lock


class TaxAndTermsService:
    """Core domain logic for Payment Terms, Tax Templates, and Advance Allocation."""

    def __init__(self, ledger_engine: LedgerEngine | None = None):
        self.ledger_engine = ledger_engine or LedgerEngine(validate_masters=False)

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
                    reference_row=t.get("reference_row"),
                    included_in_rate=t.get("included_in_rate", False),
                    add_deduct=t.get("add_deduct", "ADD"),
                    consider_for_valuation=t.get("consider_for_valuation", False),
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
        from erp.workflows.commercial.calculation_service import TaxRowInput, calculate_tax_rows

        ordered = list(tax_details)
        normalized = []
        previous_id = None
        for idx, detail in enumerate(ordered, start=1):
            own_id = int(detail.get("row_id") or idx)
            normalized.append(TaxRowInput(
                row_id=own_id,
                charge_type=detail.get("charge_type", "On Net Total"),
                rate=Decimal(str(detail.get("rate", "0.0000"))),
                description=detail.get("description", "Tax Head"),
                account_head=detail.get("account_head", "TAX"),
                reference_row=detail.get("reference_row") or (previous_id if "Previous Row" in detail.get("charge_type", "") else None),
                actual_amount=Decimal(str(detail.get("rate", "0.0000"))) if detail.get("charge_type") == "Actual" else None,
                included_in_rate=detail.get("included_in_rate", False),
                add_deduct=detail.get("add_deduct", "ADD"),
                consider_for_valuation=detail.get("consider_for_valuation", False),
            ))
            previous_id = own_id
        result = calculate_tax_rows(net_total, Decimal("0"), normalized)
        return {
            "net_total": float(net_total),
            "total_taxes_and_charges": float(result.tax_total),
            "grand_total": float(result.grand_total),
            "valuation_adjustment": float(result.valuation_adjustment),
            "rows": [
                {"row_id": row.row_id, "account_head": row.account_head, "description": row.description,
                 "charge_type": row.charge_type, "tax_amount": float(row.amount),
                 "cumulative_total": float(row.running_total), "calculation_base": float(row.calculation_base),
                 "included_in_rate": row.included_in_rate, "add_deduct": row.add_deduct,
                 "consider_for_valuation": row.consider_for_valuation}
                for row in result.rows
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
        """Apply a previously posted customer deposit to an open invoice.

        The transfer consumes the held customer-advance liability and credits
        accounts receivable; it never invents a deposit or changes invoice
        state without a journal transaction.
        """
        if allocated_amount <= Decimal("0"):
            raise ValueError("Allocated advance amount must be positive.")

        await acquire_advisory_xact_lock(
            session, "customer-advance", f"{tenant_id}:{customer_id}:currency-agnostic"
        )
        # Use the same lock namespace as bank settlements, so an advance and a
        # bank payment cannot both spend the same invoice balance concurrently.
        await acquire_advisory_xact_lock(session, "sales-invoice", str(invoice_id))

        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.invoice_id == invoice_id,
            SalesInvoice.tenant_id == tenant_id,
            SalesInvoice.customer_id == customer_id,
        ).with_for_update()
        invoice = (await session.execute(inv_stmt)).scalars().first()
        if invoice is None:
            raise ValueError("Sales invoice must belong to this workspace and customer.")
        if invoice.status in {"PAID", "CANCELLED"}:
            raise ValueError("Only an open sales invoice can receive an advance allocation.")

        unapplied_legacy_allocations = await session.scalar(select(func.count()).select_from(
            AdvancePaymentAllocation
        ).where(
            AdvancePaymentAllocation.tenant_id == tenant_id,
            AdvancePaymentAllocation.customer_id == customer_id,
            AdvancePaymentAllocation.invoice_id == invoice_id,
            AdvancePaymentAllocation.ledger_posted.is_(False),
        ))
        if unapplied_legacy_allocations:
            raise ValueError("This invoice has legacy advance allocations without ledger postings; reconcile them before allocating more.")

        outstanding = await session.scalar(select(func.coalesce(func.sum(
            GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount
        ), 0)).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.account_code == "1200-AR-CUSTOMERS",
            GeneralLedgerEntry.party_type == "CUSTOMER",
            GeneralLedgerEntry.party_id == customer_id,
            GeneralLedgerEntry.currency == invoice.currency,
            GeneralLedgerEntry.against_document_type == "SALES_INVOICE",
            GeneralLedgerEntry.against_document_id == invoice_id,
        ))
        if outstanding is None or outstanding <= Decimal("0"):
            raise ValueError("Invoice has no posted, outstanding receivable to settle.")
        if allocated_amount > outstanding:
            raise ValueError(f"Allocation amount {allocated_amount} exceeds invoice outstanding balance {outstanding}.")

        advance_balance = await session.scalar(select(func.coalesce(func.sum(
            GeneralLedgerEntry.credit_amount - GeneralLedgerEntry.debit_amount
        ), 0)).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.account_code == "2150-CUSTOMER-ADVANCES",
            GeneralLedgerEntry.party_type == "CUSTOMER",
            GeneralLedgerEntry.party_id == customer_id,
            GeneralLedgerEntry.currency == invoice.currency,
            GeneralLedgerEntry.against_document_id.is_(None),
        ))
        if advance_balance is None or advance_balance <= Decimal("0"):
            raise ValueError("No posted customer advance is available for allocation.")
        if allocated_amount > advance_balance:
            raise ValueError(f"Allocation amount {allocated_amount} exceeds available customer advance {advance_balance}.")

        allocation = AdvancePaymentAllocation(
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            allocated_amount=allocated_amount,
            reference_note=reference_note or f"Advance reconciliation against {getattr(invoice, 'invoice_number', 'INV')}",
            posting_date=date.today(),
        )
        session.add(allocation)
        await session.flush()

        proposal = TransactionProposal(
            tenant_id=tenant_id,
            posting_date=allocation.posting_date,
            currency=invoice.currency,
            source_document_type="ADVANCE_PAYMENT_ALLOCATION",
            source_document_id=allocation.allocation_id,
            entries=[
                LedgerLineProposal(
                    account_code="2150-CUSTOMER-ADVANCES",
                    cost_center="SALES-GLOBAL",
                    party_type="CUSTOMER", party_id=customer_id,
                    debit_amount=allocated_amount,
                    credit_amount=Decimal("0.0000"),
                    currency=invoice.currency,
                ),
                LedgerLineProposal(
                    account_code="1200-AR-CUSTOMERS",
                    cost_center="SALES-GLOBAL",
                    party_type="CUSTOMER", party_id=customer_id,
                    against_document_type="SALES_INVOICE", against_document_id=invoice_id,
                    debit_amount=Decimal("0.0000"),
                    credit_amount=allocated_amount,
                    currency=invoice.currency,
                ),
            ],
            human_in_the_loop_approved=True,
            agent_id="CUSTOMER_ADVANCE_ALLOCATION",
            verification_context={"reference_note": allocation.reference_note or ""},
        )
        await self.ledger_engine.commit_transaction(session, proposal)
        allocation.ledger_posted = True

        new_outstanding = outstanding - allocated_amount
        if new_outstanding <= Decimal("0"):
            invoice.status = "PAID"
        else:
            # Open balance remains authoritative; keep lifecycle in the
            # supported ISSUED state so remaining receivables stay matchable.
            invoice.status = "ISSUED"

        await session.flush()
        return allocation
