"""Supplier OTIF Scorecard and Dynamic Safety Stock Buffer Adjuster."""

from decimal import Decimal

from pydantic import BaseModel


class SupplierVarianceEvaluation(BaseModel):
    supplier_code: str
    baseline_lead_time_variance: Decimal
    current_lead_time_variance: Decimal
    variance_growth_percentage: Decimal
    triggers_buffer_expansion: bool
    safety_stock_expansion_multiplier: Decimal


class SupplierScorecardManager:
    """Tracks supplier performance and dynamically adjusts safety stock buffers."""

    EXPANSION_THRESHOLD_PERCENT = Decimal("15.00")  # > 15% lead-time variance

    @staticmethod
    def evaluate_lead_time_drift(
        supplier_code: str,
        baseline_variance: Decimal,
        current_variance: Decimal,
    ) -> SupplierVarianceEvaluation:
        """Expands safety stock multiplier if supplier delivery variance increases by >15%."""
        if baseline_variance <= 0:
            growth = Decimal("0.0000")
        else:
            growth = ((current_variance - baseline_variance) / baseline_variance) * 100

        triggers = growth > SupplierScorecardManager.EXPANSION_THRESHOLD_PERCENT

        if triggers:
            # Multiplier scales proportionally to drift (e.g. +20% variance -> 1.20x buffer)
            mult = Decimal("1.0000") + (growth / Decimal("100.0000"))
        else:
            mult = Decimal("1.0000")

        return SupplierVarianceEvaluation(
            supplier_code=supplier_code,
            baseline_lead_time_variance=baseline_variance,
            current_lead_time_variance=current_variance,
            variance_growth_percentage=growth.quantize(Decimal("0.01")),
            triggers_buffer_expansion=triggers,
            safety_stock_expansion_multiplier=mult.quantize(Decimal("0.0001")),
        )


supplier_scorecard = SupplierScorecardManager()
