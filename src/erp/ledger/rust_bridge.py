"""Deterministic Ledger Invariant Engine (PRD §General Ledger Engine).

Provides high-performance in-memory validation of financial transactions
with strict zero-sum balancing, single-sided constraints, and autonomy ceilings
via deterministic Python Decimal arithmetic, mirroring crates/ledger_core specifications.
"""


from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from erp.ledger.exceptions import (
    NegativeAmountViolation,
    SingleSidedViolation,
    ZeroSumViolation,
)
from erp.ledger.invariants import LedgerLineProposal

PRECISION = Decimal("0.0001")


class AutonomyTier(str, Enum):
    AUTONOMOUS = "AUTONOMOUS"              # <= $2,500
    DUAL_SUPERVISOR = "DUAL_SUPERVISOR"    # <= $25,000
    HUMAN_MANDATORY = "HUMAN_MANDATORY"    # > $25,000


def validate_ledger_entry_invariants(lines: list[LedgerLineProposal]) -> Decimal:
    """Validates that SUM(Debits) == SUM(Credits), strictly positive, single-sided.

    Returns the total transaction volume (sum of debits).
    Raises ZeroSumViolation, NegativeAmountViolation, or SingleSidedViolation on failure.
    """
    if not lines:
        raise ZeroSumViolation(
            debit_sum=Decimal("0.0000"),
            credit_sum=Decimal("0.0000"),
            difference=Decimal("0.0000"),
        )

    total_debits = Decimal("0.0000")
    total_credits = Decimal("0.0000")

    for line in lines:
        debit = line.debit_amount.quantize(PRECISION, rounding=ROUND_HALF_UP)
        credit = line.credit_amount.quantize(PRECISION, rounding=ROUND_HALF_UP)

        if debit < 0 or credit < 0:
            raise NegativeAmountViolation(
                f"Ledger lines cannot have negative amounts: debit={debit}, credit={credit}"
            )

        # Single-sided invariant: debit XOR credit
        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise SingleSidedViolation(
                f"Line item on account {line.account_code} must be strictly single-sided (debit XOR credit): debit={debit}, credit={credit}"
            )

        total_debits += debit
        total_credits += credit

    diff = (total_debits - total_credits).quantize(PRECISION, rounding=ROUND_HALF_UP)
    if diff != Decimal("0.0000"):
        raise ZeroSumViolation(
            debit_sum=total_debits,
            credit_sum=total_credits,
            difference=diff,
        )

    return total_debits


def evaluate_autonomy_tier(amount: Decimal) -> AutonomyTier:
    """Evaluates transaction autonomy tier against financial governance thresholds."""
    tier1_ceiling = Decimal("2500.0000")
    tier2_ceiling = Decimal("25000.0000")

    if amount <= tier1_ceiling:
        return AutonomyTier.AUTONOMOUS
    elif amount <= tier2_ceiling:
        return AutonomyTier.DUAL_SUPERVISOR
    else:
        return AutonomyTier.HUMAN_MANDATORY
