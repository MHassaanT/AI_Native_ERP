"""Stochastic Dynamic Reorder Point (ROP) Engine (PRD §Inventory Replenishment)."""

import math
from decimal import Decimal

from pydantic import BaseModel

# Standard normal distribution quantile for 99.0% service level availability
Z_99_PERCENT = Decimal("2.33")


class ROPEvaluation(BaseModel):
    item_code: str
    daily_demand_mean: Decimal
    daily_demand_std: Decimal
    lead_time_mean_days: Decimal
    lead_time_std_days: Decimal
    z_score: Decimal = Z_99_PERCENT
    lead_time_demand: Decimal
    safety_stock: Decimal
    reorder_point: Decimal


class DynamicROPEngine:
    """Calculates continuous stochastic reorder points incorporating demand and lead-time distributions."""

    @staticmethod
    def calculate_rop(
        item_code: str,
        mu_d: Decimal,
        sigma_d: Decimal,
        mu_l: Decimal,
        sigma_l: Decimal,
        z: Decimal = Z_99_PERCENT,
    ) -> ROPEvaluation:
        """Evaluates: ROP = (mu_D * mu_L) + Z * sqrt(mu_L * sigma_D^2 + mu_D^2 * sigma_L^2)."""
        lead_time_demand = mu_d * mu_l

        # Variance component under uncertainty of both demand and lead time:
        # Var = mu_L * sigma_D^2 + mu_D^2 * sigma_L^2
        variance = (mu_l * (sigma_d**2)) + ((mu_d**2) * (sigma_l**2))
        std_dev_ltd = Decimal(str(math.sqrt(float(variance))))

        safety_stock = (z * std_dev_ltd).quantize(Decimal("0.0001"))
        rop = (lead_time_demand + safety_stock).quantize(Decimal("0.0001"))

        return ROPEvaluation(
            item_code=item_code,
            daily_demand_mean=mu_d,
            daily_demand_std=sigma_d,
            lead_time_mean_days=mu_l,
            lead_time_std_days=sigma_l,
            z_score=z,
            lead_time_demand=lead_time_demand.quantize(Decimal("0.0001")),
            safety_stock=safety_stock,
            reorder_point=rop,
        )


rop_engine = DynamicROPEngine()
