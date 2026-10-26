from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from erp.db.models.inventory import Item
from erp.db.models.phase_b import PricingRule, PromotionalScheme
from erp.workflows.commercial.calculation_service import (
    CalculationLineInput, CommercialCalculationService, TaxRowInput, calculate_tax_rows,
)


def test_tax_rows_support_chained_previous_total_and_deduction():
    result = calculate_tax_rows(
        Decimal("100.0000"),
        Decimal("2"),
        [
            TaxRowInput(1, "On Net Total", Decimal("10"), "VAT", "2200-VAT"),
            TaxRowInput(2, "On Previous Row Total", Decimal("5"), "Surcharge", "2210-SUR", reference_row=1),
            TaxRowInput(3, "On Item Quantity", Decimal("1.25"), "Eco fee", "2220-ECO", add_deduct="DEDUCT"),
        ],
    )
    assert [row.amount for row in result.rows] == [Decimal("10.0000"), Decimal("5.5000"), Decimal("2.5000")]
    assert result.grand_total == Decimal("113.0000")
    assert result.tax_total == Decimal("13.0000")


def test_inclusive_tax_is_reported_without_being_added_twice():
    result = calculate_tax_rows(
        Decimal("110.0000"), Decimal("1"),
        [TaxRowInput(1, "On Net Total", Decimal("10"), "VAT inclusive", "2200-VAT", included_in_rate=True)],
    )
    assert result.rows[0].amount == Decimal("10.0000")
    assert result.grand_total == Decimal("110.0000")


def test_previous_row_reference_must_exist_and_be_prior():
    with pytest.raises(ValueError, match="earlier row"):
        calculate_tax_rows(
            Decimal("100"), Decimal("1"),
            [TaxRowInput(1, "On Previous Row Amount", Decimal("5"), "invalid", "x", reference_row=2)],
        )


class _ScalarsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _CommercialSession:
    def __init__(self, items, promotion):
        self.items = items
        self.promotion = promotion

    async def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is Item:
            return next(item for item in self.items.values() if item.item_id not in self._paid_ids)
        return None

    async def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is Item:
            self._paid_ids = {item_id for item_id, item in self.items.items() if item.item_id == self.promotion.item_id or item.item_group_id == self.promotion.item_group_id}
            if not self._paid_ids:
                self._paid_ids = set(list(self.items)[:1])
            return _ScalarsResult([self.items[item_id] for item_id in self._paid_ids])
        if entity is PricingRule:
            return _ScalarsResult([])
        if entity is PromotionalScheme:
            return _ScalarsResult([self.promotion])
        return _ScalarsResult([])


@pytest.mark.asyncio
async def test_buy_x_get_y_promotion_creates_zero_rate_tenant_item_line():
    tenant_id, item_id, free_item_id, group_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    paid_item = SimpleNamespace(item_id=item_id, item_group_id=group_id, standard_rate=Decimal("12"), weight_per_unit=Decimal("1"))
    free_item = SimpleNamespace(item_id=free_item_id, item_group_id=None, standard_rate=Decimal("8"), weight_per_unit=Decimal("0.5"))
    promotion = SimpleNamespace(
        scheme_id=uuid.uuid4(), scheme_type="BUY_X_GET_Y", discount_type="PERCENT",
        discount_value=Decimal("0"), item_id=None, item_group_id=group_id,
        valid_from=None, valid_to=None, buy_quantity=Decimal("2"),
        free_quantity=Decimal("1"), free_item_id=free_item_id,
    )
    session = _CommercialSession({item_id: paid_item, free_item_id: free_item}, promotion)

    result = await CommercialCalculationService().calculate(
        session, tenant_id=tenant_id, context="SELLING", currency="USD",
        lines=[CalculationLineInput(item_id=item_id, quantity=Decimal("4"), unit_price=Decimal("12"))],
    )

    assert result.subtotal == Decimal("48.0000")
    assert len(result.lines) == 2
    free_line = next(line for line in result.lines if line.is_free)
    assert free_line.item_id == free_item_id
    assert free_line.entered_quantity == Decimal("2")
    assert free_line.base_rate == Decimal("0")
    assert free_line.stock_quantity == Decimal("2.0000")
    assert free_line.promotion_id == promotion.scheme_id
