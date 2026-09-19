"""Real-Time BOM Landed Cost Rollup Engine (PRD §Pricing Strategy)."""

import logging
from decimal import Decimal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BOMCostRollupResult(BaseModel):
    parent_sku: str
    old_raw_material_cost: Decimal
    new_raw_material_cost: Decimal
    cost_increase_percentage: Decimal
    requires_quote_revaluation: bool


class BOMCostRollupEngine:
    """Recalculates parent assembly landed costs when supplier raw material prices change."""

    @staticmethod
    def calculate_bom_cost_delta(
        parent_sku: str,
        material_deltas: dict[str, tuple[Decimal, Decimal, Decimal]],
        # Dict mapping component_sku -> (unit_quantity, old_unit_price, new_unit_price)
    ) -> BOMCostRollupResult:
        """Rolls up component cost spikes into the parent product assembly."""
        old_total = Decimal("0.0000")
        new_total = Decimal("0.0000")

        for _comp, (qty, old_p, new_p) in material_deltas.items():
            old_total += qty * old_p
            new_total += qty * new_p

        if old_total > 0:
            growth = ((new_total - old_total) / old_total) * 100
        else:
            growth = Decimal("0.0000")

        growth_dec = growth.quantize(Decimal("0.01"))
        requires_reval = new_total > old_total

        return BOMCostRollupResult(
            parent_sku=parent_sku,
            old_raw_material_cost=old_total.quantize(Decimal("0.0001")),
            new_raw_material_cost=new_total.quantize(Decimal("0.0001")),
            cost_increase_percentage=growth_dec,
            requires_quote_revaluation=requires_reval,
        )


bom_rollup_engine = BOMCostRollupEngine()
