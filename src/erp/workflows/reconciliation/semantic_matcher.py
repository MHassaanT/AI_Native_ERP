"""Hybrid Semantic and Exact Bank Reconciliation Matcher (PRD §Bank Reconciliation)."""

import logging
import uuid
from decimal import Decimal
from difflib import SequenceMatcher

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.sales import Customer

logger = logging.getLogger(__name__)


class CandidateMatch(BaseModel):
    order_id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    customer_name: str
    order_amount: Decimal
    currency: str = "USD"
    amount_difference: Decimal
    semantic_similarity: float
    composite_confidence: float = Field(..., ge=0.0, le=1.0)
    match_status: str  # AUTO_MATCH, AMBIGUOUS, NO_MATCH


class ReconciliationMatchResult(BaseModel):
    transaction_amount: Decimal
    counterparty: str
    narrative: str
    candidates: list[CandidateMatch]
    best_match: CandidateMatch | None = None
    meets_auto_clear_threshold: bool = False


class SemanticReconciler:
    """Matches raw bank transactions against open customer receivables using hybrid semantic scoring."""

    AUTO_CLEAR_CONFIDENCE_THRESHOLD = 0.92

    async def find_matching_receivable(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        amount: Decimal,
        counterparty: str,
        narrative: str = "",
        currency: str | None = None,
    ) -> ReconciliationMatchResult:
        """Finds open, posted customer invoices matching the bank payment.

        Confirmed orders are not receivables: only an invoice with an attributed
        AR balance can safely be cleared from an incoming bank transaction.
        """
        from erp.db.models.sales import SalesInvoice

        # Query open sales invoices for tenant
        inv_stmt = (
            select(SalesInvoice, Customer.customer_name)
            .join(Customer, SalesInvoice.customer_id == Customer.customer_id)
            .where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.status == "ISSUED",
            )
        )
        inv_results = (await session.execute(inv_stmt)).all()

        # An ISSUED status alone is not evidence of an outstanding balance.
        # Require an explicit, party-attributed AR control movement and compute
        # the remaining balance from it (including partial payments/credits).
        balances_stmt = (
            select(
                GeneralLedgerEntry.against_document_id,
                GeneralLedgerEntry.currency,
                func.sum(GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.party_type == "CUSTOMER",
                GeneralLedgerEntry.party_id.is_not(None),
                GeneralLedgerEntry.against_document_type == "SALES_INVOICE",
                GeneralLedgerEntry.against_document_id.is_not(None),
                GeneralLedgerEntry.account_code == "1200-AR-CUSTOMERS",
            )
            .group_by(GeneralLedgerEntry.against_document_id, GeneralLedgerEntry.currency)
        )
        balance_rows = (await session.execute(balances_stmt)).all()
        open_balances = {
            (invoice_id, currency): balance
            for invoice_id, currency, balance in balance_rows
            if balance > Decimal("0.01")
        }

        candidates: list[CandidateMatch] = []

        for inv, cust_name in inv_results:
            outstanding = open_balances.get((inv.invoice_id, inv.currency))
            # Do not auto-clear against invoices whose posting is absent or
            # whose receivable has already been settled.
            if outstanding is None or amount <= 0 or amount > outstanding + Decimal("0.01"):
                continue
            if currency is not None and inv.currency != currency:
                continue
            amt_diff = abs(outstanding - amount)
            amt_score = 1.0 if amt_diff <= Decimal("0.01") else (0.8 if amt_diff <= Decimal("10.00") else max(0.0, 1.0 - float(amt_diff / (inv.total_amount or 1))))
            s1 = SequenceMatcher(None, counterparty.lower(), cust_name.lower()).ratio()
            s2 = 1.0 if inv.invoice_number.lower() in narrative.lower() else 0.0
            semantic_score = max(s1, s2)
            composite = (amt_score * 0.60) + (semantic_score * 0.40)
            status = "AUTO_MATCH" if composite >= self.AUTO_CLEAR_CONFIDENCE_THRESHOLD else ("AMBIGUOUS" if composite >= 0.60 else "NO_MATCH")
            candidates.append(
                CandidateMatch(
                    order_id=inv.invoice_id,
                    order_number=inv.invoice_number,
                    customer_id=inv.customer_id,
                    customer_name=cust_name,
                    order_amount=outstanding,
                    currency=inv.currency,
                    amount_difference=amt_diff,
                    semantic_similarity=round(semantic_score, 4),
                    composite_confidence=round(composite, 4),
                    match_status=status,
                )
            )


        # Sort candidates descending by confidence
        candidates.sort(key=lambda c: c.composite_confidence, reverse=True)
        top_candidates = candidates[:3]

        best_match = (
            top_candidates[0]
            if top_candidates and top_candidates[0].composite_confidence >= 0.60
            else None
        )
        auto_clear = (
            best_match is not None
            and best_match.composite_confidence >= self.AUTO_CLEAR_CONFIDENCE_THRESHOLD
        )

        return ReconciliationMatchResult(
            transaction_amount=amount,
            counterparty=counterparty,
            narrative=narrative,
            candidates=top_candidates,
            best_match=best_match,
            meets_auto_clear_threshold=auto_clear,
        )


semantic_reconciler = SemanticReconciler()
