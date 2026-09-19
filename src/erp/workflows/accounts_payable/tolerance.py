"""3-Way Matching Tolerance and Mathematical Invariant Evaluator (PRD §Accounts Payable)."""

from decimal import Decimal

from pydantic import BaseModel, Field

PRICE_TOLERANCE_LIMIT = Decimal("0.0100")  # 1.0% allowable price variance


class LineItemMatchEvaluation(BaseModel):
    item_code: str
    is_sku_matched: bool
    invoice_qty: Decimal
    grn_qty: Decimal
    is_qty_compliant: bool
    invoice_unit_price: Decimal
    po_unit_price: Decimal
    price_variance_percentage: Decimal
    is_price_compliant: bool
    is_line_matched: bool
    discrepancy_reason: str | None = None


class ThreeWayToleranceSummary(BaseModel):
    is_fully_matched: bool
    overall_variance_percentage: Decimal
    discrepancies: list[str] = Field(default_factory=list)
    line_evaluations: list[LineItemMatchEvaluation] = Field(default_factory=list)


def evaluate_three_way_tolerances(
    invoice_lines: list[dict],
    po_lines: list[dict],
    grn_lines: list[dict],
) -> ThreeWayToleranceSummary:
    """Evaluates 3-way matching invariants across Invoice, PO, and GRN line items."""
    po_item_map = {line["item_code"]: line for line in po_lines}
    grn_item_map = {line["item_code"]: line for line in grn_lines}

    line_evals = []
    discrepancies = []
    max_price_var = Decimal("0.0000")

    for inv_line in invoice_lines:
        code = inv_line["item_code"]
        inv_qty = Decimal(str(inv_line["quantity"]))
        inv_price = Decimal(str(inv_line["unit_price"]))

        # 1. SKU Identity Match = 100%
        if code not in po_item_map:
            discrepancies.append(
                f"SKU mismatch: Item '{code}' on invoice does not exist in Purchase Order."
            )
            line_evals.append(
                LineItemMatchEvaluation(
                    item_code=code,
                    is_sku_matched=False,
                    invoice_qty=inv_qty,
                    grn_qty=Decimal("0.0000"),
                    is_qty_compliant=False,
                    invoice_unit_price=inv_price,
                    po_unit_price=Decimal("0.0000"),
                    price_variance_percentage=Decimal("100.0000"),
                    is_price_compliant=False,
                    is_line_matched=False,
                    discrepancy_reason=f"SKU '{code}' not on PO",
                )
            )
            continue

        po_line = po_item_map[code]
        po_price = Decimal(str(po_line["unit_price"]))

        # 2. Quantity(Invoice) <= Quantity(GRN)
        grn_line = grn_item_map.get(code)
        grn_qty = Decimal(str(grn_line["quantity"])) if grn_line else Decimal("0.0000")
        is_qty_valid = inv_qty <= grn_qty
        if not is_qty_valid:
            discrepancies.append(
                f"Quantity violation on '{code}': Billed {inv_qty} exceeds warehouse received {grn_qty}."
            )

        # 3. |Price(Inv) - Price(PO)| / Price(PO) <= 1.0% (0.010)
        if po_price > 0:
            price_diff = abs(inv_price - po_price)
            variance_pct = price_diff / po_price
        else:
            variance_pct = Decimal("0.0000")

        if variance_pct > max_price_var:
            max_price_var = variance_pct

        is_price_valid = variance_pct <= PRICE_TOLERANCE_LIMIT
        if not is_price_valid:
            discrepancies.append(
                f"Price variance on '{code}': {variance_pct * 100:.2f}% exceeds allowable 1.00% tolerance "
                f"(Invoice: ${inv_price}, PO: ${po_price})."
            )

        line_valid = is_qty_valid and is_price_valid
        line_evals.append(
            LineItemMatchEvaluation(
                item_code=code,
                is_sku_matched=True,
                invoice_qty=inv_qty,
                grn_qty=grn_qty,
                is_qty_compliant=is_qty_valid,
                invoice_unit_price=inv_price,
                po_unit_price=po_price,
                price_variance_percentage=(variance_pct * 100).quantize(Decimal("0.0001")),
                is_price_compliant=is_price_valid,
                is_line_matched=line_valid,
                discrepancy_reason="; ".join(discrepancies[-2:]) if not line_valid else None,
            )
        )

    is_all_matched = len(discrepancies) == 0 and len(line_evals) > 0

    return ThreeWayToleranceSummary(
        is_fully_matched=is_all_matched,
        overall_variance_percentage=(max_price_var * 100).quantize(Decimal("0.0001")),
        discrepancies=discrepancies,
        line_evaluations=line_evals,
    )
