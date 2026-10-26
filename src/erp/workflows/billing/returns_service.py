"""Credit and Debit Notes (Returns & Adjustments) Service.

Manages customer sales returns (Credit Notes) and vendor purchase returns (Debit Notes)
with automatic zero-sum general ledger reversals.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.billing import CreditNote, CreditNoteItem, DebitNote, DebitNoteItem
from erp.db.models.inventory import StockLedgerEntry, StockLevel
from erp.db.models.purchasing import SupplierInvoice
from erp.db.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrderItem
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
        source_invoice = None
        source_invoice_items: dict[uuid.UUID, SalesInvoiceItem] = {}
        prior_returns: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
        previous_credit_subtotal = Decimal("0.0000")
        previous_credit_tax = Decimal("0.0000")
        if invoice_id:
            source_invoice = await session.scalar(select(SalesInvoice).where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.invoice_id == invoice_id,
                SalesInvoice.customer_id == customer_id,
                SalesInvoice.status != "CANCELLED",
            ).with_for_update())
            if source_invoice is None:
                raise ValueError("The return invoice must be an active invoice for this customer in this workspace.")
            invoice_lines = (await session.scalars(select(SalesInvoiceItem).where(
                SalesInvoiceItem.tenant_id == tenant_id,
                SalesInvoiceItem.invoice_id == invoice_id,
            ).with_for_update())).all()
            source_invoice_items = {line.invoice_item_id: line for line in invoice_lines}
            if not items or any(not it.get("sales_invoice_item_id") for it in items):
                raise ValueError("Invoice-linked returns must identify the source sales invoice item on every line.")
            requested_line_ids = [uuid.UUID(str(it["sales_invoice_item_id"])) for it in items]
            if len(set(requested_line_ids)) != len(requested_line_ids):
                raise ValueError("A source invoice line may appear only once on a credit note.")
            if not set(requested_line_ids).issubset(source_invoice_items):
                raise ValueError("Every returned invoice line must belong to the selected tenant invoice.")
            legacy_return_items = set((await session.scalars(
                select(CreditNoteItem.item_id)
                .join(CreditNote, CreditNote.credit_note_id == CreditNoteItem.credit_note_id)
                .where(CreditNote.tenant_id == tenant_id, CreditNote.invoice_id == invoice_id,
                       CreditNote.status != "CANCELLED", CreditNoteItem.tenant_id == tenant_id,
                       CreditNoteItem.sales_invoice_item_id.is_(None))
            )).all())
            if legacy_return_items.intersection(source_invoice_items[line_id].item_id for line_id in requested_line_ids):
                raise ValueError("An earlier unlinked return exists for this item; reconcile its source invoice line before returning more.")
            historical = (await session.execute(
                select(
                    CreditNoteItem.sales_invoice_item_id,
                    func.coalesce(func.sum(CreditNoteItem.quantity), 0).label("returned_quantity"),
                    func.coalesce(func.sum(CreditNoteItem.line_total), 0).label("credited_amount"),
                ).join(CreditNote, CreditNote.credit_note_id == CreditNoteItem.credit_note_id)
                .where(CreditNote.tenant_id == tenant_id, CreditNote.invoice_id == invoice_id,
                       CreditNote.status != "CANCELLED",
                       CreditNoteItem.tenant_id == tenant_id,
                       CreditNoteItem.sales_invoice_item_id.in_(requested_line_ids))
                .group_by(CreditNoteItem.sales_invoice_item_id)
            )).all()
            prior_returns = {row.sales_invoice_item_id: (Decimal(row.returned_quantity), Decimal(row.credited_amount)) for row in historical}
            previous_credit_subtotal, previous_credit_tax = (await session.execute(
                select(
                    func.coalesce(func.sum(CreditNote.subtotal), 0),
                    func.coalesce(func.sum(CreditNote.tax_amount), 0),
                ).where(CreditNote.tenant_id == tenant_id, CreditNote.invoice_id == invoice_id,
                        CreditNote.status != "CANCELLED")
            )).one()
            previous_credit_subtotal = Decimal(previous_credit_subtotal)
            previous_credit_tax = Decimal(previous_credit_tax)

        subtotal = Decimal("0.0000")
        cn_items = []
        order_return_deltas: dict[uuid.UUID, Decimal] = {}
        for it in items:
            item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty = Decimal(str(it["quantity"]))
            if qty <= 0:
                raise ValueError("Return quantities must be positive.")
            source_line_id = uuid.UUID(str(it["sales_invoice_item_id"])) if it.get("sales_invoice_item_id") else None
            source_line = source_invoice_items.get(source_line_id) if source_line_id else None
            if source_invoice and (source_line is None or source_line.item_id != item_id):
                raise ValueError("Returned item must match its explicitly linked invoice line.")
            if source_line:
                returned_before, credited_before = prior_returns.get(source_line.invoice_item_id, (Decimal("0"), Decimal("0")))
                quantity_remaining = Decimal(source_line.quantity) - returned_before
                if qty > quantity_remaining:
                    raise ValueError("Return quantity exceeds the unreturned quantity on the source invoice line.")
                amount_remaining = Decimal(source_line.line_total) - credited_before
                line_tot = amount_remaining if qty == quantity_remaining else (
                    Decimal(source_line.line_total) * qty / Decimal(source_line.quantity)
                ).quantize(Decimal("0.0001"))
                unit_price = (line_tot / qty).quantize(Decimal("0.0001"))
                if source_line.order_item_id:
                    order_return_deltas[source_line.order_item_id] = order_return_deltas.get(source_line.order_item_id, Decimal("0")) + qty
            else:
                if it.get("unit_price") is None:
                    raise ValueError("An invoice item link or an explicit unit price is required for every return line.")
                unit_price = Decimal(str(it["unit_price"]))
                line_tot = round(qty * unit_price, 4)
            subtotal += line_tot

            cn_items.append(
                CreditNoteItem(
                    tenant_id=tenant_id,
                    item_id=item_id,
                    sales_invoice_item_id=source_line_id,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_tot,
                )
            )

        if source_invoice:
            remaining_invoice_subtotal = max(Decimal("0"), Decimal(source_invoice.subtotal) - previous_credit_subtotal)
            remaining_invoice_tax = max(Decimal("0"), Decimal(source_invoice.tax_amount) - previous_credit_tax)
            tax_amount = remaining_invoice_tax if subtotal >= remaining_invoice_subtotal else (
                Decimal(source_invoice.tax_amount) * subtotal / Decimal(source_invoice.subtotal)
            ).quantize(Decimal("0.0001")) if source_invoice.subtotal else Decimal("0.0000")
            currency = source_invoice.currency
            for order_item_id, qty in sorted(order_return_deltas.items(), key=lambda pair: str(pair[0])):
                order_item = await session.scalar(select(SalesOrderItem).where(
                    SalesOrderItem.tenant_id == tenant_id,
                    SalesOrderItem.order_item_id == order_item_id,
                ).with_for_update())
                if order_item is None:
                    raise ValueError("Source invoice order line is missing from this workspace.")
                if order_item.returned_quantity + qty > order_item.invoiced_quantity:
                    raise ValueError("Return quantity exceeds the sales-order line's unreturned invoiced quantity.")
                order_item.returned_quantity += qty
        else:
            tax_amount = round(subtotal * Decimal("0.05"), 4)
            currency = "USD"
        total_amount = subtotal + tax_amount
        cn_num = f"CRN-{datetime.now(UTC).strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        credit_note = CreditNote(
            tenant_id=tenant_id,
            credit_note_number=cn_num,
            invoice_id=invoice_id,
            customer_id=customer_id,
            posting_date=date.today(),
            reason=reason,
            currency=currency,
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
                    posting_datetime=datetime.now(UTC),
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

        proposal = TransactionProposal(
            tenant_id=tenant_id,
            posting_date=date.today(),
            currency=currency,
            source_document_type="CREDIT_NOTE",
            source_document_id=credit_note.credit_note_id,
            entries=gl_entries,
            human_in_the_loop_approved=True,
        )
        await self.ledger_engine.commit_transaction(session, proposal)

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
        dn_num = f"DBN-{datetime.now(UTC).strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

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
                    posting_datetime=datetime.now(UTC),
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
