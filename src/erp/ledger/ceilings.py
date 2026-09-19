"""Autonomous Financial Ceilings and Policy Routing (PRD §Guardrails)."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from erp.config import settings
from erp.ledger.exceptions import AutonomyCeilingExceeded


class AutonomyTier(StrEnum):
    TIER_1 = "TIER_1"  # < 2,500 USD: Fully autonomous
    TIER_2 = "TIER_2"  # 2,500 to 25,000 USD: Autonomous with supervisory alert
    TIER_3 = "TIER_3"  # > 25,000 USD: Requires Human-in-the-Loop approval


class CeilingEvaluationResult(BaseModel):
    tier: AutonomyTier
    total_amount: Decimal
    requires_human_approval: bool
    requires_notification: bool
    is_approved: bool


def evaluate_autonomy_tier(
    total_amount: Decimal,
    human_approved: bool = False,
    tier1_ceiling: Decimal | None = None,
    tier2_ceiling: Decimal | None = None,
) -> CeilingEvaluationResult:
    """Evaluates transaction total against statutory autonomy ceilings."""
    t1 = tier1_ceiling or settings.LEDGER_TIER1_CEILING
    t2 = tier2_ceiling or settings.LEDGER_TIER2_CEILING

    if total_amount < t1:
        return CeilingEvaluationResult(
            tier=AutonomyTier.TIER_1,
            total_amount=total_amount,
            requires_human_approval=False,
            requires_notification=False,
            is_approved=True,
        )
    elif total_amount <= t2:
        return CeilingEvaluationResult(
            tier=AutonomyTier.TIER_2,
            total_amount=total_amount,
            requires_human_approval=False,
            requires_notification=True,
            is_approved=True,
        )
    else:
        if not human_approved:
            raise AutonomyCeilingExceeded(
                total_amount=total_amount,
                ceiling_amount=t2,
                tier=AutonomyTier.TIER_3.value,
            )
        return CeilingEvaluationResult(
            tier=AutonomyTier.TIER_3,
            total_amount=total_amount,
            requires_human_approval=True,
            requires_notification=True,
            is_approved=True,
        )
