"""Automated 3-Way Matching Engine (PRD §Accounts Payable)."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)
from erp.events.outbox import OutboxManager
from erp.ledger.engine import LedgerCommitResult, TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
from erp.workflows.accounts_payable.dispute_generator import (
    VendorDisputeNotice,
    dispute_generator,
)
from erp.workflows.accounts_payable.tolerance import (
    ThreeWayToleranceSummary,
    evaluate_three_way_tolerances,
)

logger = logging.getLogger(__name__)


class ThreeWayMatchResult(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    is_matched: bool
    matching_status: str
    tolerance_summary: ThreeWayToleranceSummary
    ledger_result: LedgerCommitResult | None = None
    dispute_notice: VendorDisputeNotice | None = None


class ThreeWayMatcher:
    """Executes automated 3-way matching across Supplier Invoices, Purchase Orders, and GRNs."""

    async def match_invoice(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        po_id: uuid.UUID | None = None,
        grn_id: uuid.UUID | None = None,
    ) -> ThreeWayMatchResult:
        """Executes 3-way matching and either commits ledger settlement or triggers dispute notice."""
        # 1. Fetch Invoice
        inv_stmt = select(SupplierInvoice).where(
            SupplierInvoice.tenant_id == tenant_id,
            SupplierInvoice.invoice_id == invoice_id,
        )
        invoice = (await session.execute(inv_stmt)).scalar_one_or_none()
        if not invoice:
            raise ValueError(f"Supplier invoice '{invoice_id}' not found.")

        # If already matched and posted, return matched result to avoid duplicate postings
        if invoice.matching_status == "MATCHED":
            return ThreeWayMatchResult(
                invoice_id=invoice.invoice_id,
                invoice_number=invoice.invoice_number,
                is_matched=True,
                matching_status="MATCHED",
                tolerance_summary=ThreeWayToleranceSummary(
                    is_fully_matched=True,
                    overall_variance_percentage=invoice.variance_percentage,
                    discrepancies=[],
                ),
                ledger_result=None,
                dispute_notice=None,
            )

        target_po_id = po_id or invoice.po_id
        if not target_po_id:
            raise ValueError(
                f"Cannot perform 3-way match: invoice '{invoice.invoice_number}' is not linked to a Purchase Order."
            )

        # 2. Fetch Supplier
        sup = (
            await session.execute(
                select(Supplier).where(
                    Supplier.tenant_id == tenant_id,
                    Supplier.supplier_id == invoice.supplier_id,
                )
            )
        ).scalar_one_or_none()
        if not sup:
            raise ValueError(f"Supplier for invoice '{invoice.invoice_number}' not found.")

        # 3. Dynamic GRN Resolution:
        # Check if an explicit grn_id was passed, or if the PO has a recorded GRN
        target_grn_id = grn_id
        if not target_grn_id and target_po_id:
            po_grn = (
                await session.execute(
                    select(GoodsReceiptNote)
                    .where(
                        GoodsReceiptNote.tenant_id == tenant_id,
                        GoodsReceiptNote.po_id == target_po_id,
                    )
                    .order_by(GoodsReceiptNote.created_at.desc())
                )
            ).scalars().first()
            if po_grn:
                target_grn_id = po_grn.grn_id
                invoice.grn_id = target_grn_id

        if not target_grn_id and invoice.grn_id:
            # Check if invoice.grn_id belongs to target_po_id
            stored_grn = (
                await session.execute(
                    select(GoodsReceiptNote).where(
                        GoodsReceiptNote.tenant_id == tenant_id,
                        GoodsReceiptNote.grn_id == invoice.grn_id,
                    )
                )
            ).scalar_one_or_none()
            if stored_grn and stored_grn.po_id == target_po_id:
                target_grn_id = invoice.grn_id

        # If no GRN exists for this PO yet, mark DISPUTED gracefully
        if not target_grn_id:
            invoice.matching_status = "DISPUTED"
            invoice.variance_percentage = Decimal("0.0000")
            discrepancy_msg = (
                "Missing Goods Receipt Note (GRN): Goods have not been received or confirmed into warehouse stock."
            )
            invoice.dispute_reason = discrepancy_msg

            tolerance = ThreeWayToleranceSummary(
                is_fully_matched=False,
                overall_variance_percentage=Decimal("0.0000"),
                quantity_variance_percentage=Decimal("100.0000"),
                price_variance_percentage=Decimal("0.0000"),
                discrepancies=[discrepancy_msg],
                line_evaluations=[],
            )

            dispute_doc = dispute_generator.generate_notice(
                invoice_number=invoice.invoice_number,
                supplier_code=sup.supplier_code,
                supplier_name=sup.supplier_name,
                tolerance_summary=tolerance,
            )

            await OutboxManager.enqueue_event(
                session=session,
                tenant_id=tenant_id,
                aggregate_type="INVOICE",
                aggregate_id=str(invoice.invoice_id),
                event_type="erp.supplychain.invoice_disputed",
                payload={
                    "invoice_number": invoice.invoice_number,
                    "supplier_code": sup.supplier_code,
                    "variance_percentage": "0.0000",
                    "dispute_id": dispute_doc.dispute_id,
                },
            )
            logger.warning(
                "3-way match FAILED for invoice %s (missing GRN). Marked DISPUTED.",
                invoice.invoice_number,
            )
            await session.flush()
            return ThreeWayMatchResult(
                invoice_id=invoice.invoice_id,
                invoice_number=invoice.invoice_number,
                is_matched=False,
                matching_status=invoice.matching_status,
                tolerance_summary=tolerance,
                ledger_result=None,
                dispute_notice=dispute_doc,
            )

        # 4. Fetch Purchase Order and Line Items
        po = (
            await session.execute(
                select(PurchaseOrder).where(
                    PurchaseOrder.tenant_id == tenant_id,
                    PurchaseOrder.po_id == target_po_id,
                )
            )
        ).scalar_one()

        po_lines_db = (
            await session.execute(
                select(PurchaseOrderItem, Item.item_code)
                .join(Item, PurchaseOrderItem.item_id == Item.item_id)
                .where(
                    PurchaseOrderItem.tenant_id == tenant_id,
                    PurchaseOrderItem.po_id == target_po_id,
                )
            )
        ).all()

        po_lines = [
            {
                "item_code": code,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
            }
            for line, code in po_lines_db
        ]

        # 5. Fetch GRN
        grn = (
            await session.execute(
                select(GoodsReceiptNote).where(
                    GoodsReceiptNote.tenant_id == tenant_id,
                    GoodsReceiptNote.grn_id == target_grn_id,
                )
            )
        ).scalar_one()

        # Fetch actual GRN line items from DB
        grn_items_db = (
            await session.execute(
                select(GoodsReceiptNoteItem, Item.item_code)
                .join(Item, GoodsReceiptNoteItem.item_id == Item.item_id)
                .where(
                    GoodsReceiptNoteItem.tenant_id == tenant_id,
                    GoodsReceiptNoteItem.grn_id == target_grn_id,
                )
            )
        ).all()

        if grn_items_db:
            grn_lines = [
                {
                    "item_code": code,
                    "quantity": line.quantity_received,
                    "unit_price": line.unit_price,
                }
                for line, code in grn_items_db
            ]
        else:
            # Fallback if GRN was recorded without line items
            grn_lines = po_lines.copy()

        # Fetch actual Supplier Invoice line items from DB
        inv_items_db = (
            await session.execute(
                select(SupplierInvoiceItem).where(
                    SupplierInvoiceItem.tenant_id == tenant_id,
                    SupplierInvoiceItem.invoice_id == invoice.invoice_id,
                )
            )
        ).scalars().all()

        if inv_items_db:
            inv_lines = [
                {
                    "item_code": line.item_code,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                }
                for line in inv_items_db
            ]
        else:
            first_sku = po_lines[0]["item_code"] if po_lines else "RAW-MATERIAL"
            first_qty = po_lines[0]["quantity"] if po_lines else Decimal("1.0000")
            inv_lines = [
                {
                    "item_code": first_sku,
                    "quantity": first_qty,
                    "unit_price": (invoice.total_amount / max(first_qty, Decimal("1.0000"))).quantize(Decimal("0.0001")),
                }
            ]


        # 5. Evaluate tolerances
        tolerance = evaluate_three_way_tolerances(
            invoice_lines=inv_lines,
            po_lines=po_lines,
            grn_lines=grn_lines,
        )

        ledger_commit = None
        dispute_doc = None

        if tolerance.is_fully_matched:
            # Update invoice record to MATCHED
            invoice.matching_status = "MATCHED"
            invoice.variance_percentage = tolerance.overall_variance_percentage
            invoice.dispute_reason = None

            # Stage AP Journal Entry to Ledger Engine
            # Debit: 1300-RAW-MATERIALS, Credit: 2100-AP-VENDORS
            entries = [
                LedgerLineProposal(
                    account_code="1300-RAW-MATERIALS",
                    cost_center="PLANT-01",
                    debit_amount=invoice.total_amount,
                    credit_amount=Decimal("0.0000"),
                    currency=invoice.currency,
                ),
                LedgerLineProposal(
                    account_code="2100-AP-VENDORS",
                    cost_center="CORP-FINANCE",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=invoice.total_amount,
                    currency=invoice.currency,
                ),
            ]

            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=date.today(),
                currency=invoice.currency,
                source_document_type="AUTOMATED_AP_MATCH",
                source_document_id=invoice.invoice_id,
                entries=entries,
                human_in_the_loop_approved=False,
                agent_id="SUPPLY_CHAIN_AP",
                verification_context={
                    "po_number": po.po_number,
                    "grn_number": grn.grn_number,
                    "variance_percentage": str(tolerance.overall_variance_percentage),
                },
            )

            ledger_commit = await ledger_engine.commit_transaction(
                session=session, proposal=proposal
            )
            logger.info(
                "3-way match SUCCESS for invoice %s. Ledger committed %s",
                invoice.invoice_number,
                ledger_commit.transaction_id,
            )
        else:
            # Mark DISPUTED
            invoice.matching_status = "DISPUTED"
            invoice.variance_percentage = tolerance.overall_variance_percentage
            invoice.dispute_reason = "; ".join(tolerance.discrepancies)

            dispute_doc = dispute_generator.generate_notice(
                invoice_number=invoice.invoice_number,
                supplier_code=sup.supplier_code,
                supplier_name=sup.supplier_name,
                tolerance_summary=tolerance,
            )

            # Enqueue dispute event in outbox
            await OutboxManager.enqueue_event(
                session=session,
                tenant_id=tenant_id,
                aggregate_type="INVOICE",
                aggregate_id=str(invoice.invoice_id),
                event_type="erp.supplychain.invoice_disputed",
                payload={
                    "invoice_number": invoice.invoice_number,
                    "supplier_code": sup.supplier_code,
                    "variance_percentage": str(tolerance.overall_variance_percentage),
                    "dispute_id": dispute_doc.dispute_id,
                },
            )
            logger.warning(
                "3-way match FAILED for invoice %s. Marked DISPUTED.", invoice.invoice_number
            )

        await session.flush()

        return ThreeWayMatchResult(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            is_matched=tolerance.is_fully_matched,
            matching_status=invoice.matching_status,
            tolerance_summary=tolerance,
            ledger_result=ledger_commit,
            dispute_notice=dispute_doc,
        )


three_way_matcher = ThreeWayMatcher()
