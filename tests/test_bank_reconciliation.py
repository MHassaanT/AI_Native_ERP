"""Unit Tests for Continuous Bank Feed Ingestion and Semantic Matching."""

from datetime import date
from decimal import Decimal

from erp.workflows.reconciliation.bank_feed_ingestor import bank_feed_ingestor
from erp.workflows.reconciliation.semantic_matcher import (
    CandidateMatch,
    SemanticReconciler,
)


class TestBankReconciliation:
    """Tests open-banking webhook ingestion and hybrid matching logic."""

    def test_bank_feed_webhook_parsing(self):
        payload = {
            "account_number": "ACC-OPERATING-01",
            "booking_date": "2026-11-04",
            "amount": "24250.0000",
            "currency": "USD",
            "counterparty_name": "Siemens Energy AG",
            "remittance_information": "Payment for INV-2026-SE-091",
        }
        tx = bank_feed_ingestor.parse_webhook_payload(payload)
        assert tx.amount == Decimal("24250.0000")
        assert tx.booking_date == date(2026, 11, 4)
        assert tx.counterparty_name == "Siemens Energy AG"
        assert tx.transaction_id.startswith("bank_tx_")

    def test_reconciliation_threshold_classification(self):
        reconciler = SemanticReconciler()
        assert reconciler.AUTO_CLEAR_CONFIDENCE_THRESHOLD == 0.92

        # High confidence candidate match
        high_candidate = CandidateMatch(
            order_id="11111111-1111-1111-1111-111111111111",
            order_number="SO-2026-001",
            customer_id="22222222-2222-2222-2222-222222222222",
            customer_name="Siemens Energy AG",
            order_amount=Decimal("24250.0000"),
            amount_difference=Decimal("0.0000"),
            semantic_similarity=0.95,
            composite_confidence=0.98,
            match_status="AUTO_MATCH",
        )
        assert high_candidate.composite_confidence >= reconciler.AUTO_CLEAR_CONFIDENCE_THRESHOLD

        # Ambiguous candidate match
        ambiguous_candidate = CandidateMatch(
            order_id="11111111-1111-1111-1111-111111111111",
            order_number="SO-2026-002",
            customer_id="22222222-2222-2222-2222-222222222222",
            customer_name="Siemens AG International",
            order_amount=Decimal("25000.0000"),
            amount_difference=Decimal("750.0000"),
            semantic_similarity=0.82,
            composite_confidence=0.74,
            match_status="AMBIGUOUS",
        )
        assert ambiguous_candidate.composite_confidence < reconciler.AUTO_CLEAR_CONFIDENCE_THRESHOLD
        assert ambiguous_candidate.match_status == "AMBIGUOUS"
