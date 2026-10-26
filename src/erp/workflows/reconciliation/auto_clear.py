"""Continuous Bank Reconciliation Auto-Clearing Engine (PRD §Bank Reconciliation)."""

import logging
import uuid
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.sales import SalesInvoice
from erp.db.models.ledger import GeneralLedgerEntry
from erp.ledger.engine import LedgerCommitResult, TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
from erp.ledger.locks import acquire_advisory_xact_lock
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
    ledger_transaction_id: uuid.UUID | None = None
    reconciliation_worklist_item: dict | None = None


def bank_transaction_source_id(tenant_id: uuid.UUID, tx: RawBankTransaction) -> uuid.UUID:
    """Create a stable ledger source key from a provider transaction ID."""
    return uuid.uuid5(tenant_id, f"bank-feed:{tx.account_number}:{tx.transaction_id}")


class AutoClearingEngine:
    """Evaluates incoming bank transactions and automatically posts clearing entries to General Ledger."""

    async def process_bank_transaction(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        tx: RawBankTransaction,
    ) -> AutoClearResult:
        """Processes bank transaction through hybrid matching and auto-clears if threshold is met."""
        source_id = bank_transaction_source_id(tenant_id, tx)
        await acquire_advisory_xact_lock(session, "bank-transaction", str(source_id))

        # Provider transaction IDs are stable across retries. Return the first
        # posting instead of applying a duplicate credit to the receivable.
        prior_stmt = select(GeneralLedgerEntry).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.source_document_type == "AUTO_BANK_RECONCILIATION",
            GeneralLedgerEntry.source_document_id == source_id,
            GeneralLedgerEntry.account_code == "1020-BANK-OPERATING",
        )
        prior = (await session.execute(prior_stmt)).scalars().first()
        if prior is not None:
            linked_invoice_id = await session.scalar(
                select(GeneralLedgerEntry.against_document_id).where(
                    GeneralLedgerEntry.tenant_id == tenant_id,
                    GeneralLedgerEntry.transaction_id == prior.transaction_id,
                    GeneralLedgerEntry.against_document_type == "SALES_INVOICE",
                    GeneralLedgerEntry.against_document_id.is_not(None),
                ).limit(1)
            )
            invoice_number = await session.scalar(
                select(SalesInvoice.invoice_number).where(
                    SalesInvoice.tenant_id == tenant_id,
                    SalesInvoice.invoice_id == linked_invoice_id,
                )
            ) if linked_invoice_id else None
            if prior.currency == tx.currency and prior.debit_amount == tx.amount:
                return AutoClearResult(
                    transaction_id=tx.transaction_id,
                    amount=tx.amount,
                    is_auto_cleared=True,
                    matched_order_number=invoice_number,
                    ledger_transaction_id=prior.transaction_id,
                )
            return AutoClearResult(
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                is_auto_cleared=False,
                reconciliation_worklist_item={
                    "transaction_id": tx.transaction_id,
                    "status": "IDEMPOTENCY_KEY_CONFLICT",
                    "message": "This bank transaction ID was already posted with a different amount or currency.",
                },
            )

        # Step 1: Hybrid matching
        match_res = await semantic_reconciler.find_matching_receivable(
            session=session,
            tenant_id=tenant_id,
            amount=tx.amount,
            counterparty=tx.counterparty_name,
            narrative=tx.remittance_information,
            currency=tx.currency,
        )

        def worklist_result() -> AutoClearResult:
            worklist_item = {
                "transaction_id": tx.transaction_id,
                "amount": str(tx.amount),
                "counterparty": tx.counterparty_name,
                "remittance_info": tx.remittance_information,
                "booking_date": tx.booking_date.isoformat(),
                "candidates": [c.model_dump(mode="json") for c in match_res.candidates],
                "status": "AWAITING_HUMAN_CONFIRMATION",
            }
            return AutoClearResult(
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                is_auto_cleared=False,
                confidence_score=match_res.best_match.composite_confidence
                if match_res.best_match
                else 0.0,
                reconciliation_worklist_item=worklist_item,
            )

        if match_res.meets_auto_clear_threshold and match_res.best_match:
            best = match_res.best_match

            # The matcher returns invoice IDs only. Recheck tenant, customer,
            # currency and lifecycle before posting so an order or stale
            # candidate can never be represented as an invoice settlement.
            inv_stmt = select(SalesInvoice).where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.invoice_id == best.order_id,
                SalesInvoice.customer_id == best.customer_id,
                SalesInvoice.currency == tx.currency,
                SalesInvoice.status == "ISSUED",
            )
            inv = (await session.execute(inv_stmt)).scalar_one_or_none()
            if inv is None or tx.amount > best.order_amount + Decimal("0.01"):
                return worklist_result()

            # Serialize settlements for the invoice and re-read its balance;
            # two concurrent feeds must not both clear the same open amount.
            await acquire_advisory_xact_lock(session, "sales-invoice", str(inv.invoice_id))
            outstanding = await session.scalar(
                select(func.coalesce(func.sum(
                    GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount
                ), 0)).where(
                    GeneralLedgerEntry.tenant_id == tenant_id,
                    GeneralLedgerEntry.account_code == "1200-AR-CUSTOMERS",
                    GeneralLedgerEntry.party_type == "CUSTOMER",
                    GeneralLedgerEntry.party_id == inv.customer_id,
                    GeneralLedgerEntry.currency == inv.currency,
                    GeneralLedgerEntry.against_document_type == "SALES_INVOICE",
                    GeneralLedgerEntry.against_document_id == inv.invoice_id,
                )
            )
            if outstanding is None or outstanding <= Decimal("0.01") or tx.amount > outstanding + Decimal("0.01"):
                return worklist_result()

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
                    party_type="CUSTOMER", party_id=best.customer_id,
                    against_document_type="SALES_INVOICE", against_document_id=inv.invoice_id,
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
                source_document_id=source_id,
                entries=entries,
                human_in_the_loop_approved=False,
                agent_id="FINANCIAL_CONTROLLER_RECON",
                verification_context={
                    "bank_tx_id": tx.transaction_id,
                    "counterparty": tx.counterparty_name,
                    "confidence_score": str(best.composite_confidence),
                    "invoice_number": inv.invoice_number,
                },
            )

            commit = await ledger_engine.commit_transaction(session=session, proposal=proposal)

            # Keep partial settlements open; status is only a full-payment
            # summary and never changes the sales-order lifecycle.
            if tx.amount >= best.order_amount - Decimal("0.01"):
                inv.status = "PAID"


            logger.info(
                "Bank feed auto-cleared invoice %s (confidence=%.2f). Ledger txn: %s",
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
                ledger_transaction_id=commit.transaction_id,
            )
        else:
            logger.info("Bank feed placed in worklist for human review (confidence < 0.92)")
            return worklist_result()


auto_clearing_engine = AutoClearingEngine()
