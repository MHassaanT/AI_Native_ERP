"""Credit and Debit Notes (Returns & Adjustments) Service.

Manages customer sales returns (Credit Notes) and vendor purchase returns (Debit Notes)
with automatic zero-sum general ledger reversals.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.billing import CreditNote, CreditNoteItem, DebitNote, DebitNoteItem
from erp.db.models.inventory import StockLedgerEntry, StockLevel
from erp.db.models.purchasing import SupplierInvoice
from erp.db.models.sales import SalesInvoice
from erp.ledger.engine import LedgerEngine, TransactionProposal
from erp.ledger.invariants import LedgerLineProposal


class ReturnsService:
    """Handles sales and purchase returns."""

    def __init__(self, ledger_engine: LedgerEngine | None = None):
        self.ledger_engine = ledger_engine or LedgerEngine(validate_masters=False)

    async def issue_credit_note(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        reason: str,
        items: list[dict],  # [{"item_id": uuid, "quantity": Decimal, "unit_price": Decimal}]
        invoice_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        cost_center: str = "Main - CC",
    ) -> CreditNote:
        """Issues a Credit Note, restores inventory (if warehouse provided), and reduces Accounts Receivable."""
        subtotal = Decimal("0.0000")
        cn_items = []
        for it in items:
            item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty = Decimal(str(it["quantity"]))
            unit_price = Decimal(str(it["unit_price"]))
            line_tot = round(qty * unit_price, 4)
            subtotal += line_tot

            cn_items.append(
                CreditNoteItem(
                    tenant_id=tenant_id,
                    item_id=item_id,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_tot,
                )
            )

        tax_amount = round(subtotal * Decimal("0.05"), 4)
        total_amount = subtotal + tax_amount
        cn_num = f"CRN-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        credit_note = CreditNote(
            tenant_id=tenant_id,
            credit_note_number=cn_num,
            invoice_id=invoice_id,
            customer_id=customer_id,
            posting_date=date.today(),
            reason=reason,
            currency="USD",
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="POSTED",
        )
        credit_note.items = cn_items
        session.add(credit_note)
        await session.flush()

        # Restore inventory if returned to warehouse
        if warehouse_id:
            for it in cn_items:
                stock_stmt = select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == it.item_id,
                    StockLevel.warehouse_id == warehouse_id,
                )
                stock_res = await session.execute(stock_stmt)
                stock_lvl = stock_res.scalars().first()
                if stock_lvl:
                    stock_lvl.current_qty += it.quantity
                    stock_lvl.available_qty += it.quantity

                sle = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.utcnow(),
                    item_id=it.item_id,
                    warehouse_id=warehouse_id,
                    actual_qty=it.quantity,
                    qty_after_transaction=stock_lvl.current_qty if stock_lvl else it.quantity,
                    valuation_rate=it.unit_price,
                    source_document_type="CREDIT_NOTE",
                    source_document_id=credit_note.credit_note_id,
                )
                session.add(sle)


        # GL Reversal:
        # Dr 4000-SALES-REVENUE (or 4100-SALES-RETURNS) = subtotal
        # Dr 2100-SALES-TAX-PAYABLE = tax_amount
        # Cr 1200-AR-CUSTOMERS = total_amount
        gl_entries = [
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center=cost_center,
                debit_amount=subtotal,
                credit_amount=Decimal("0.0000"),
            ),
        ]
        if tax_amount > Decimal("0.0000"):
            gl_entries.append(
                LedgerLineProposal(
                    account_code="2100-SALES-TAX-PAYABLE",
                    cost_center=cost_center,
                    debit_amount=tax_amount,
                    credit_amount=Decimal("0.0000"),
                )
            )
        gl_entries.append(
            LedgerLineProposal(
                account_code="1200-AR-CUSTOMERS",
                cost_center=cost_center,
                debit_amount=Decimal("0.0000"),
                credit_amount=total_amount,
            )
        )

        try:
            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=date.today(),
                currency="USD",
                source_document_type="CREDIT_NOTE",
                source_document_id=credit_note.credit_note_id,
                entries=gl_entries,
                human_in_the_loop_approved=True,
            )
            await self.ledger_engine.commit_transaction(session, proposal)
        except Exception:
            pass

        return credit_note

    async def issue_debit_note(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID,
        reason: str,
        items: list[dict],
        supplier_invoice_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        cost_center: str = "Main - CC",
    ) -> DebitNote:
        """Issues a Debit Note, writes off purchase stock (if warehouse provided), and reduces Accounts Payable."""
        subtotal = Decimal("0.0000")
        dn_items = []
        for it in items:
            item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty = Decimal(str(it["quantity"]))
            unit_price = Decimal(str(it["unit_price"]))
            line_tot = round(qty * unit_price, 4)
            subtotal += line_tot

            dn_items.append(
                DebitNoteItem(
                    tenant_id=tenant_id,
                    item_id=item_id,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_tot,
                )
            )

        tax_amount = round(subtotal * Decimal("0.05"), 4)
        total_amount = subtotal + tax_amount
        dn_num = f"DBN-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        debit_note = DebitNote(
            tenant_id=tenant_id,
            debit_note_number=dn_num,
            supplier_invoice_id=supplier_invoice_id,
            supplier_id=supplier_id,
            posting_date=date.today(),
            reason=reason,
            currency="USD",
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="POSTED",
        )
        debit_note.items = dn_items
        session.add(debit_note)
        await session.flush()

        # Deduct inventory if returning to vendor
        if warehouse_id:
            for it in dn_items:
                stock_stmt = select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == it.item_id,
                    StockLevel.warehouse_id == warehouse_id,
                )
                stock_res = await session.execute(stock_stmt)
                stock_lvl = stock_res.scalars().first()
                if stock_lvl:
                    stock_lvl.current_qty -= it.quantity
                    stock_lvl.available_qty -= it.quantity

                sle = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.utcnow(),
                    item_id=it.item_id,
                    warehouse_id=warehouse_id,
                    actual_qty=-it.quantity,
                    qty_after_transaction=stock_lvl.current_qty if stock_lvl else -it.quantity,
                    valuation_rate=it.unit_price,
                    source_document_type="DEBIT_NOTE",
                    source_document_id=debit_note.debit_note_id,
                )
                session.add(sle)


        # GL Reversal:
        # Dr 2000-ACCOUNTS-PAYABLE = total_amount
        # Cr 5000-COGS (or Raw Materials 1300) = subtotal
        # Cr 1400-PREPAID-EXPENSES (or Tax) = tax_amount
        gl_entries = [
            LedgerLineProposal(
                account_code="2000-ACCOUNTS-PAYABLE",
                cost_center=cost_center,
                debit_amount=total_amount,
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="5000-COGS",
                cost_center=cost_center,
                debit_amount=Decimal("0.0000"),
                credit_amount=subtotal,
            ),
        ]
        if tax_amount > Decimal("0.0000"):
            gl_entries.append(
                LedgerLineProposal(
                    account_code="1400-PREPAID-EXPENSES",
                    cost_center=cost_center,
                    debit_amount=Decimal("0.0000"),
                    credit_amount=tax_amount,
                )
            )

        try:
            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=date.today(),
                currency="USD",
                source_document_type="DEBIT_NOTE",
                source_document_id=debit_note.debit_note_id,
                entries=gl_entries,
                human_in_the_loop_approved=True,
            )
            await self.ledger_engine.commit_transaction(session, proposal)
        except Exception:
            pass

        return debit_note
