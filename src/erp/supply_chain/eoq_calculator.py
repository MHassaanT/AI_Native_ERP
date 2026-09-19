"""Economic Order Quantity (EOQ) Calculator (PRD §Inventory Replenishment)."""

import math
from decimal import Decimal

from pydantic import BaseModel


class EOQResult(BaseModel):
    item_code: str
    annual_demand: Decimal
    order_cost: Decimal
    holding_cost_per_unit: Decimal
    economic_order_quantity: Decimal
    recommended_order_quantity: Decimal


class EOQCalculator:
    """Calculates optimal batch size minimizing total ordering and inventory holding costs."""

    @staticmethod
    def calculate_eoq(
        item_code: str,
        annual_demand: Decimal,
        order_cost: Decimal = Decimal("150.00"),
        holding_cost_per_unit: Decimal = Decimal("0.85"),
        batch_multiple: Decimal = Decimal("100.00"),
    ) -> EOQResult:
        """Evaluates: EOQ = sqrt( (2 * D * S) / H )."""
        if annual_demand <= 0 or holding_cost_per_unit <= 0:
            return EOQResult(
                item_code=item_code,
                annual_demand=annual_demand,
                order_cost=order_cost,
                holding_cost_per_unit=holding_cost_per_unit,
                economic_order_quantity=Decimal("0.0000"),
                recommended_order_quantity=Decimal("0.0000"),
            )

        raw_eoq = math.sqrt(
            (2.0 * float(annual_demand) * float(order_cost)) / float(holding_cost_per_unit)
        )
        eoq_dec = Decimal(str(raw_eoq)).quantize(Decimal("0.0001"))

        # Round up to nearest batch multiple if specified
        if batch_multiple > 0:
            batches = math.ceil(float(eoq_dec) / float(batch_multiple))
            rec_qty = Decimal(str(batches)) * batch_multiple
        else:
            rec_qty = eoq_dec

        return EOQResult(
            item_code=item_code,
            annual_demand=annual_demand,
            order_cost=order_cost,
            holding_cost_per_unit=holding_cost_per_unit,
            economic_order_quantity=eoq_dec,
            recommended_order_quantity=rec_qty,
        )


eoq_calculator = EOQCalculator()
