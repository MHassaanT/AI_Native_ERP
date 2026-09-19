"""Unit Tests for Deterministic Ledger Engine Invariants and Ceilings."""

from decimal import Decimal

import pytest

from erp.ledger.ceilings import AutonomyTier, evaluate_autonomy_tier
from erp.ledger.exceptions import (
    AutonomyCeilingExceeded,
    NegativeAmountViolation,
    SingleSidedViolation,
    ZeroSumViolation,
)
from erp.ledger.invariants import LedgerLineProposal, validate_zero_sum


class TestLedgerInvariants:
    """Tests double-entry mathematical invariants."""

    def test_balanced_transaction_succeeds(self):
        entries = [
            LedgerLineProposal(
                account_code="1020-BANK-OPERATING",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("1500.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center="SALES-GLOBAL",
                debit_amount=Decimal("0.0000"),
                credit_amount=Decimal("1500.0000"),
            ),
        ]
        total = validate_zero_sum(entries)
        assert total == Decimal("1500.0000")

    def test_multi_line_split_balanced_transaction(self):
        entries = [
            LedgerLineProposal(
                account_code="1020-BANK-OPERATING",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("1000.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="1200-AR-CUSTOMERS",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("500.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center="SALES-GLOBAL",
                debit_amount=Decimal("0.0000"),
                credit_amount=Decimal("1500.0000"),
            ),
        ]
        total = validate_zero_sum(entries)
        assert total == Decimal("1500.0000")

    def test_unbalanced_transaction_raises_zero_sum_violation(self):
        entries = [
            LedgerLineProposal(
                account_code="1020-BANK-OPERATING",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("1500.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center="SALES-GLOBAL",
                debit_amount=Decimal("0.0000"),
                credit_amount=Decimal("1499.9900"),
            ),
        ]
        with pytest.raises(ZeroSumViolation) as exc_info:
            validate_zero_sum(entries)
        assert exc_info.value.difference == Decimal("0.0100")

    def test_single_sided_line_violation(self):
        entries = [
            LedgerLineProposal(
                account_code="1020-BANK-OPERATING",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("500.0000"),
                credit_amount=Decimal("500.0000"),  # Both non-zero
            ),
        ]
        with pytest.raises(SingleSidedViolation):
            validate_zero_sum(entries)

    def test_negative_amount_violation(self):
        entries = [
            LedgerLineProposal(
                account_code="1020-BANK-OPERATING",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("-500.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center="SALES-GLOBAL",
                debit_amount=Decimal("0.0000"),
                credit_amount=Decimal("-500.0000"),
            ),
        ]
        with pytest.raises(NegativeAmountViolation):
            validate_zero_sum(entries)

    def test_arbitrary_precision_stress(self):
        """Simulates 1,000 sub-cent fractional line items to verify zero float drift."""
        entries = []
        unit = Decimal("0.0001")
        count = 1000
        for i in range(count):
            entries.append(
                LedgerLineProposal(
                    account_code=f"10{i % 10}0-ACC",
                    cost_center="CORP-FINANCE",
                    debit_amount=unit,
                    credit_amount=Decimal("0.0000"),
                )
            )
        entries.append(
            LedgerLineProposal(
                account_code="2100-AP-VENDORS",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("0.0000"),
                credit_amount=unit * count,
            )
        )
        total = validate_zero_sum(entries)
        assert total == Decimal("0.1000")


class TestAutonomyCeilings:
    """Tests statutory financial autonomy tiers."""

    def test_tier_1_sub_2500_auto_commits(self):
        result = evaluate_autonomy_tier(Decimal("1200.5000"), human_approved=False)
        assert result.tier == AutonomyTier.TIER_1
        assert result.is_approved is True
        assert result.requires_human_approval is False
        assert result.requires_notification is False

    def test_tier_2_between_2500_and_25000_requires_notification(self):
        result = evaluate_autonomy_tier(Decimal("18450.0000"), human_approved=False)
        assert result.tier == AutonomyTier.TIER_2
        assert result.is_approved is True
        assert result.requires_human_approval is False
        assert result.requires_notification is True

    def test_tier_3_over_25000_blocks_without_approval(self):
        with pytest.raises(AutonomyCeilingExceeded) as exc_info:
            evaluate_autonomy_tier(Decimal("50000.0000"), human_approved=False)
        assert exc_info.value.total_amount == Decimal("50000.0000")
        assert exc_info.value.tier == AutonomyTier.TIER_3.value

    def test_tier_3_over_25000_succeeds_with_human_approval(self):
        result = evaluate_autonomy_tier(Decimal("50000.0000"), human_approved=True)
        assert result.tier == AutonomyTier.TIER_3
        assert result.is_approved is True
        assert result.requires_human_approval is True
