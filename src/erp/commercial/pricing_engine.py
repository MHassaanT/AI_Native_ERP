"""Margin-Defended Dynamic Pricing Engine (PRD §Pricing Strategy)."""

import logging
from decimal import Decimal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

MINIMUM_CONTRIBUTION_MARGIN_FLOOR = Decimal("0.2200")  # 22.0% corporate gross margin floor


class DynamicPricingEvaluation(BaseModel):
    sku: str
    bom_raw_material_cost: Decimal
    machine_depreciation_cost: Decimal
    direct_labor_cost: Decimal
    dynamic_freight_cost: Decimal
    total_landed_cost: Decimal
    minimum_margin_floor: Decimal = MINIMUM_CONTRIBUTION_MARGIN_FLOOR
    minimum_floor_price: Decimal
    proposed_unit_price: Decimal
    computed_margin_percentage: Decimal
    is_margin_defended: bool
    requires_price_escalation: bool


class DynamicPricingEngine:
    """Calculates landed component costs and defends the 22% contribution margin floor."""

    @staticmethod
    def calculate_margin_defended_price(
        sku: str,
        bom_material_cost: Decimal,
        machine_depreciation: Decimal = Decimal("4.5000"),
        direct_labor: Decimal = Decimal("6.0000"),
        freight: Decimal = Decimal("1.2500"),
        target_markup_multiplier: Decimal = Decimal("1.3500"),
    ) -> DynamicPricingEvaluation:
        """Calculates landed cost and minimum floor price: Floor = Landed / (1 - 0.22)."""
        landed_cost = bom_material_cost + machine_depreciation + direct_labor + freight

        # Minimum floor price defending 22% margin:
        # Margin = (Price - Cost) / Price >= 0.22  =>  Price >= Cost / (1 - 0.22)
        divisor = Decimal("1.0000") - MINIMUM_CONTRIBUTION_MARGIN_FLOOR
        floor_price = (landed_cost / divisor).quantize(Decimal("0.0001"))

        # Desired price from commercial target markup
        proposed_price = (landed_cost * target_markup_multiplier).quantize(Decimal("0.0001"))
        if proposed_price < floor_price:
            proposed_price = floor_price

        # Actual margin
        actual_margin = ((proposed_price - landed_cost) / proposed_price).quantize(
            Decimal("0.0001")
        )
        is_compliant = actual_margin >= MINIMUM_CONTRIBUTION_MARGIN_FLOOR

        return DynamicPricingEvaluation(
            sku=sku,
            bom_raw_material_cost=bom_material_cost,
            machine_depreciation_cost=machine_depreciation,
            direct_labor_cost=direct_labor,
            dynamic_freight_cost=freight,
            total_landed_cost=landed_cost,
            minimum_margin_floor=MINIMUM_CONTRIBUTION_MARGIN_FLOOR,
            minimum_floor_price=floor_price,
            proposed_unit_price=proposed_price,
            computed_margin_percentage=(actual_margin * 100).quantize(Decimal("0.01")),
            is_margin_defended=is_compliant,
            requires_price_escalation=not is_compliant,
        )


pricing_engine = DynamicPricingEngine()
