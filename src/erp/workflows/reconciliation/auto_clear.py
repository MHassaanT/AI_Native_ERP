"""Continuous Bank Reconciliation Auto-Clearing Engine (PRD §Bank Reconciliation)."""

import logging
import uuid
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.sales import SalesOrder
from erp.ledger.engine import LedgerCommitResult, TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
from erp.workflows.reconciliation.bank_feed_ingestor import RawBankTransaction
from erp.workflows.reconciliation.semantic_matcher import (
    semantic_reconciler,
)

logger = logging.getLogger(__name__)


class AutoClearResult(BaseModel):
    transaction_id: str
    amount: Decimal
    is_auto_cleared: bool
    matched_order_number: str | None = None
    confidence_score: float = 0.0
    ledger_commit: LedgerCommitResult | None = None
    reconciliation_worklist_item: dict | None = None


class AutoClearingEngine:
    """Evaluates incoming bank transactions and automatically posts clearing entries to General Ledger."""

    async def process_bank_transaction(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        tx: RawBankTransaction,
    ) -> AutoClearResult:
        """Processes bank transaction through hybrid matching and auto-clears if threshold is met."""
        # Step 1: Hybrid matching
        match_res = await semantic_reconciler.find_matching_receivable(
            session=session,
            tenant_id=tenant_id,
            amount=tx.amount,
            counterparty=tx.counterparty_name,
            narrative=tx.remittance_information,
        )

        if match_res.meets_auto_clear_threshold and match_res.best_match:
            best = match_res.best_match

            # Stage clearing entries:
            # Debit: 1020-BANK-OPERATING, Credit: 1200-AR-CUSTOMERS
            entries = [
                LedgerLineProposal(
                    account_code="1020-BANK-OPERATING",
                    cost_center="CORP-FINANCE",
                    debit_amount=tx.amount,
                    credit_amount=Decimal("0.0000"),
                    currency=tx.currency,
                ),
                LedgerLineProposal(
                    account_code="1200-AR-CUSTOMERS",
                    cost_center="SALES-GLOBAL",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=tx.amount,
                    currency=tx.currency,
                ),
            ]

            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=tx.booking_date,
                currency=tx.currency,
                source_document_type="AUTO_BANK_RECONCILIATION",
                source_document_id=best.order_id,
                entries=entries,
                human_in_the_loop_approved=False,
                agent_id="FINANCIAL_CONTROLLER_RECON",
                verification_context={
                    "bank_tx_id": tx.transaction_id,
                    "counterparty": tx.counterparty_name,
                    "confidence_score": str(best.composite_confidence),
                    "order_number": best.order_number,
                },
            )

            commit = await ledger_engine.commit_transaction(session=session, proposal=proposal)

            # Update Sales Invoice / Sales Order status
            from erp.db.models.sales import SalesInvoice
            inv_stmt = select(SalesInvoice).where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.invoice_id == best.order_id,
            )
            inv = (await session.execute(inv_stmt)).scalar_one_or_none()
            if inv:
                inv.status = "PAID"
                if inv.order_id:
                    so_stmt = select(SalesOrder).where(
                        SalesOrder.tenant_id == tenant_id,
                        SalesOrder.order_id == inv.order_id,
                    )
                    so = (await session.execute(so_stmt)).scalar_one_or_none()
                    if so:
                        so.status = "SETTLED"
            else:
                so_stmt = select(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.order_id == best.order_id,
                )
                so = (await session.execute(so_stmt)).scalar_one_or_none()
                if so:
                    so.status = "SETTLED"


            logger.info(
                "Bank feed auto-cleared order %s (confidence=%.2f). Ledger txn: %s",
                best.order_number,
                best.composite_confidence,
                commit.transaction_id,
            )

            return AutoClearResult(
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                is_auto_cleared=True,
                matched_order_number=best.order_number,
                confidence_score=best.composite_confidence,
                ledger_commit=commit,
            )
        else:
            # Place in ambiguous reconciliation worklist
            worklist_item = {
                "transaction_id": tx.transaction_id,
                "amount": str(tx.amount),
                "counterparty": tx.counterparty_name,
                "remittance_info": tx.remittance_information,
                "booking_date": tx.booking_date.isoformat(),
                "candidates": [c.model_dump(mode="json") for c in match_res.candidates],
                "status": "AWAITING_HUMAN_CONFIRMATION",
            }
            logger.info("Bank feed placed in worklist for human review (confidence < 0.92)")

            return AutoClearResult(
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                is_auto_cleared=False,
                confidence_score=match_res.best_match.composite_confidence
                if match_res.best_match
                else 0.0,
                reconciliation_worklist_item=worklist_item,
            )


auto_clearing_engine = AutoClearingEngine()
