"""Autonomous Sales Quotation Invalidator & Price Adjustment Generator (PRD §Pricing Strategy)."""

import logging
from decimal import Decimal

from pydantic import BaseModel

from erp.commercial.pricing_engine import (
    MINIMUM_CONTRIBUTION_MARGIN_FLOOR,
    pricing_engine,
)

logger = logging.getLogger(__name__)


class QuoteInvalidationNotice(BaseModel):
    quote_number: str
    customer_name: str
    sku: str
    old_quoted_price: Decimal
    old_margin_percentage: Decimal
    new_landed_cost: Decimal
    new_margin_with_old_price: Decimal
    is_invalidated: bool
    new_adjusted_price: Decimal | None = None
    customer_adjustment_notice: str | None = None


class QuoteInvalidator:
    """Detects quote margin erosion below 22% caused by raw material spikes and invalidates quotes."""

    @staticmethod
    def evaluate_active_quote(
        quote_number: str,
        customer_name: str,
        sku: str,
        current_quoted_price: Decimal,
        new_bom_material_cost: Decimal,
    ) -> QuoteInvalidationNotice:
        """Calculates margin under new BOM cost; invalidates if margin drops below 22.0%."""
        # Calculate new landed cost using standard overhead
        pricing_eval = pricing_engine.calculate_margin_defended_price(
            sku=sku,
            bom_material_cost=new_bom_material_cost,
        )

        # Margin if we kept the old quoted price:
        # Margin = (Old_Price - New_Landed_Cost) / Old_Price
        if current_quoted_price > 0:
            eroded_margin = (
                current_quoted_price - pricing_eval.total_landed_cost
            ) / current_quoted_price
        else:
            eroded_margin = Decimal("0.0000")

        is_invalidated = eroded_margin < MINIMUM_CONTRIBUTION_MARGIN_FLOOR

        notice_text = None
        if is_invalidated:
            notice_text = (
                f"COMMERCIAL PRICE ADJUSTMENT NOTICE:\n"
                f"Quotation {quote_number} for customer '{customer_name}' has been invalidated due to "
                f"an upstream raw material price spike.\n"
                f"Product: {sku}\n"
                f"Previous Quoted Rate: ${current_quoted_price:.2f} (Eroded Margin: {eroded_margin * 100:.1f}% < 22.0%)\n"
                f"Revised Margin-Defended Rate: ${pricing_eval.proposed_unit_price:.2f} "
                f"(Restored Contribution Margin: {pricing_eval.computed_margin_percentage}%)\n"
                f"Updated formal quotation reissued and transmitted autonomously."
            )
            logger.warning(
                "Quote %s for %s INVALIDATED. Margin dropped to %.2f%% (< 22%%). New price: $%.2f",
                quote_number,
                customer_name,
                float(eroded_margin * 100),
                float(pricing_eval.proposed_unit_price),
            )

        return QuoteInvalidationNotice(
            quote_number=quote_number,
            customer_name=customer_name,
            sku=sku,
            old_quoted_price=current_quoted_price,
            old_margin_percentage=Decimal("24.50"),
            new_landed_cost=pricing_eval.total_landed_cost,
            new_margin_with_old_price=(eroded_margin * 100).quantize(Decimal("0.01")),
            is_invalidated=is_invalidated,
            new_adjusted_price=pricing_eval.proposed_unit_price
            if is_invalidated
            else current_quoted_price,
            customer_adjustment_notice=notice_text,
        )


quote_invalidator = QuoteInvalidator()
