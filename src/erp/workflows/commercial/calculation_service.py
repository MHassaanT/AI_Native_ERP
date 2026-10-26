"""Tenant-scoped, deterministic pricing/UOM/shipping calculation primitives.

Documents persist the returned identifiers and values at the point at which a
draft is recalculated. Submission must consume those snapshots, never resolve
against mutable master data again.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item
from erp.db.models.phase_b import PricingRule, PromotionalScheme, ShippingRule, ShippingRuleCondition
from erp.db.models.shared_master import ItemPrice, PriceList, UOM, UOMConversion

MONEY_QUANTUM = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def total_from_tax_snapshot(base: Decimal, snapshot: list[dict] | None) -> Decimal:
    """Apply only non-inclusive tax rows to the payable document total."""
    total = base
    for row in snapshot or []:
        if row.get("included_in_rate"):
            continue
        amount = Decimal(str(row["amount"]))
        total += -amount if row.get("add_deduct") == "DEDUCT" else amount
    return _money(total)


@dataclass(frozen=True)
class CalculationLineInput:
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal | None = None
    uom_id: uuid.UUID | None = None
    price_list_id: uuid.UUID | None = None


@dataclass(frozen=True)
class CalculatedLine:
    item_id: uuid.UUID
    price_list_id: uuid.UUID | None
    entered_quantity: Decimal
    uom_id: uuid.UUID | None
    conversion_factor: Decimal
    stock_quantity: Decimal
    base_rate: Decimal
    price_list_rate: Decimal
    item_price_id: uuid.UUID | None
    pricing_rule_id: uuid.UUID | None
    promotion_id: uuid.UUID | None
    discount_amount: Decimal
    line_total: Decimal
    is_free: bool = False


@dataclass(frozen=True)
class CalculationResult:
    context: str
    currency: str
    price_list_id: uuid.UUID | None
    lines: tuple[CalculatedLine, ...]
    subtotal: Decimal
    discount_total: Decimal
    shipping_charge: Decimal
    total: Decimal
    warnings: tuple[str, ...]
    calculation_hash: str


@dataclass(frozen=True)
class TaxRowInput:
    row_id: int
    charge_type: str
    rate: Decimal
    description: str
    account_head: str
    reference_row: int | None = None
    actual_amount: Decimal | None = None
    included_in_rate: bool = False
    add_deduct: str = "ADD"
    consider_for_valuation: bool = False


@dataclass(frozen=True)
class TaxRowResult:
    row_id: int
    charge_type: str
    description: str
    account_head: str
    calculation_base: Decimal
    amount: Decimal
    running_total: Decimal
    included_in_rate: bool
    add_deduct: str
    consider_for_valuation: bool


@dataclass(frozen=True)
class TaxCalculationResult:
    rows: tuple[TaxRowResult, ...]
    tax_total: Decimal
    grand_total: Decimal
    valuation_adjustment: Decimal


def calculate_tax_rows(net_total: Decimal, total_quantity: Decimal, rows: list[TaxRowInput]) -> TaxCalculationResult:
    """Calculate legacy and ERPNext-style chained tax rows in stable row order."""
    if net_total < 0 or total_quantity < 0:
        raise ValueError("Tax calculation bases cannot be negative.")
    ordered = sorted(rows, key=lambda row: row.row_id)
    ids = [row.row_id for row in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("Tax row identifiers must be unique.")
    by_id: dict[int, TaxRowResult] = {}
    results: list[TaxRowResult] = []
    running = net_total
    tax_total = Decimal("0")
    valuation = Decimal("0")
    for row in ordered:
        kind = row.charge_type.strip().upper().replace(" ", "_")
        direction = row.add_deduct.upper()
        if direction not in {"ADD", "DEDUCT"} or row.rate < 0:
            raise ValueError("Tax rows require a non-negative rate and ADD/DEDUCT direction.")
        if kind == "ACTUAL":
            base = Decimal(row.actual_amount or row.rate)
            amount = base
        elif kind == "ON_NET_TOTAL":
            base = net_total
            if row.included_in_rate:
                amount = base * row.rate / (Decimal("100") + row.rate) if row.rate else Decimal("0")
            else:
                amount = base * row.rate / Decimal("100")
        elif kind in {"ON_PREVIOUS_ROW_AMOUNT", "ON_PREVIOUS_ROW_TOTAL"}:
            if row.reference_row is None or row.reference_row not in by_id:
                raise ValueError("Previous-row tax calculations must reference an earlier row in the same template.")
            prior = by_id[row.reference_row]
            base = prior.amount if kind == "ON_PREVIOUS_ROW_AMOUNT" else prior.running_total
            amount = base * row.rate / Decimal("100")
        elif kind == "ON_ITEM_QUANTITY":
            base = total_quantity
            amount = base * row.rate
        else:
            raise ValueError(f"Unsupported tax charge type: {row.charge_type}")
        amount = _money(amount)
        contribution = -amount if direction == "DEDUCT" else amount
        if not row.included_in_rate:
            running = _money(running + contribution)
        tax_total += contribution
        if row.consider_for_valuation:
            valuation += contribution
        result = TaxRowResult(
            row_id=row.row_id, charge_type=kind, description=row.description,
            account_head=row.account_head, calculation_base=_money(base), amount=amount,
            running_total=running, included_in_rate=row.included_in_rate,
            add_deduct=direction, consider_for_valuation=row.consider_for_valuation,
        )
        by_id[row.row_id] = result
        results.append(result)
    return TaxCalculationResult(
        rows=tuple(results), tax_total=_money(tax_total), grand_total=_money(running),
        valuation_adjustment=_money(valuation),
    )


class CommercialCalculationService:
    """Resolve eligible prices and deterministic rules for one document draft."""

    async def calculate(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        context: str,
        currency: str,
        lines: list[CalculationLineInput],
        price_list_id: uuid.UUID | None = None,
        shipping_rule_id: uuid.UUID | None = None,
        destination_country: str | None = None,
        destination_state: str | None = None,
        calculation_date: date | None = None,
    ) -> CalculationResult:
        context = context.upper()
        if context not in {"BUYING", "SELLING"}:
            raise ValueError("Calculation context must be BUYING or SELLING.")
        if not lines:
            raise ValueError("At least one commercial line is required.")
        on_date = calculation_date or date.today()
        effective_lists: dict[uuid.UUID, PriceList] = {}
        for selected_list in {line.price_list_id or price_list_id for line in lines if line.price_list_id or price_list_id}:
            plist = await session.scalar(select(PriceList).where(
                PriceList.tenant_id == tenant_id,
                PriceList.price_list_id == selected_list,
                PriceList.is_active.is_(True),
                PriceList.currency == currency,
                (PriceList.buying.is_(True) if context == "BUYING" else PriceList.selling.is_(True)),
            ))
            if plist is None:
                raise ValueError("Price list must be active, tenant-owned, context-compatible, and use the document currency.")
            effective_lists[plist.price_list_id] = plist

        item_ids = {line.item_id for line in lines}
        items = (await session.scalars(select(Item).where(
            Item.tenant_id == tenant_id, Item.item_id.in_(item_ids), Item.is_active.is_(True),
            (Item.is_purchase_item.is_(True) if context == "BUYING" else Item.is_sales_item.is_(True)),
        ))).all()
        by_item = {item.item_id: item for item in items}
        if set(by_item) != item_ids:
            raise ValueError("Every line must reference an active item allowed in this document context.")

        calculations: list[CalculatedLine] = []
        warnings: list[str] = []
        total_weight = Decimal("0")
        for line in lines:
            if line.quantity <= 0:
                raise ValueError("Line quantity must be positive.")
            item = by_item[line.item_id]
            selected_list_id = line.price_list_id or price_list_id
            plist = effective_lists.get(selected_list_id) if selected_list_id else None
            factor = Decimal("1")
            if line.uom_id:
                uom = await session.scalar(select(UOM).where(
                    UOM.tenant_id == tenant_id, UOM.uom_id == line.uom_id, UOM.is_active.is_(True),
                ))
                if uom is None:
                    raise ValueError("Line unit of measure must be active and belong to this workspace.")
                conversion = await session.scalar(select(UOMConversion).where(
                    UOMConversion.tenant_id == tenant_id,
                    UOMConversion.from_uom_id == line.uom_id,
                    UOMConversion.item_id == line.item_id,
                ))
                if conversion is None:
                    conversion = await session.scalar(select(UOMConversion).where(
                        UOMConversion.tenant_id == tenant_id,
                        UOMConversion.from_uom_id == line.uom_id,
                        UOMConversion.item_id.is_(None),
                    ))
                if conversion is None:
                    # Stock UOM is represented by the item's configured name.
                    if uom.abbreviation != item.stock_uom and uom.uom_name != item.stock_uom:
                        raise ValueError("No tenant/item UOM conversion exists for the selected unit.")
                else:
                    factor = Decimal(conversion.factor)

            item_price = None
            if plist:
                price_query = select(ItemPrice).where(
                    ItemPrice.tenant_id == tenant_id,
                    ItemPrice.item_id == line.item_id,
                    ItemPrice.price_list_id == plist.price_list_id,
                    ItemPrice.currency == currency,
                    ItemPrice.is_active.is_(True),
                    or_(ItemPrice.uom_id == line.uom_id, ItemPrice.uom_id.is_(None)),
                    or_(ItemPrice.valid_from.is_(None), ItemPrice.valid_from <= on_date),
                    or_(ItemPrice.valid_to.is_(None), ItemPrice.valid_to >= on_date),
                ).order_by(
                    (ItemPrice.uom_id == line.uom_id).desc(),
                    ItemPrice.priority.asc(),
                    ItemPrice.valid_from.desc().nullslast(),
                    ItemPrice.created_at.desc(),
                )
                price_rows = (await session.scalars(price_query)).all()
                if len(price_rows) > 1 and (
                    price_rows[0].uom_id == price_rows[1].uom_id
                    and price_rows[0].priority == price_rows[1].priority
                    and price_rows[0].valid_from == price_rows[1].valid_from
                ):
                    raise ValueError("Ambiguous overlapping item prices; retire or correct the competing price records.")
                item_price = price_rows[0] if price_rows else None
            # An explicit price list owns the rate. Manual entry remains the
            # fallback when no valid list price exists or no list was selected.
            rate = Decimal(item_price.rate) if item_price else Decimal(line.unit_price) if line.unit_price is not None else Decimal(item.standard_rate)
            if rate < 0:
                raise ValueError("Unit price cannot be negative.")

            eligible_rules = (await session.scalars(select(PricingRule).where(
                PricingRule.tenant_id == tenant_id, PricingRule.is_active.is_(True),
                or_(PricingRule.price_list_id == selected_list_id, PricingRule.price_list_id.is_(None)),
                or_(PricingRule.item_id == line.item_id, PricingRule.item_id.is_(None)),
                or_(PricingRule.item_group_id == item.item_group_id, PricingRule.item_group_id.is_(None)),
                PricingRule.min_quantity <= line.quantity,
                or_(PricingRule.valid_from.is_(None), PricingRule.valid_from <= on_date),
                or_(PricingRule.valid_to.is_(None), PricingRule.valid_to >= on_date),
            ).order_by(PricingRule.priority, PricingRule.pricing_rule_id))).all()
            if len(eligible_rules) > 1 and not all(rule.stackable for rule in eligible_rules):
                if eligible_rules[0].priority == eligible_rules[1].priority:
                    raise ValueError("Multiple pricing rules match at the same priority; mark the set stackable or resolve the ambiguity.")
                eligible_rules = eligible_rules[:1]
            applied_rules = eligible_rules
            rule = applied_rules[0] if applied_rules else None
            pre_discount = rate * line.quantity
            remaining_rate = rate
            discount = Decimal("0")
            for applied_rule in applied_rules:
                rule_discount = remaining_rate * Decimal(applied_rule.discount_value) / Decimal("100") if applied_rule.discount_type == "PERCENT" else Decimal(applied_rule.discount_value)
                rule_discount = min(_money(rule_discount), _money(remaining_rate))
                discount += rule_discount * line.quantity
                remaining_rate = max(Decimal("0"), remaining_rate - rule_discount)
            discount = min(_money(discount), _money(pre_discount))

            promotions = (await session.scalars(select(PromotionalScheme).where(
                PromotionalScheme.tenant_id == tenant_id, PromotionalScheme.is_active.is_(True),
                or_(PromotionalScheme.item_id == line.item_id,
                    PromotionalScheme.item_group_id == item.item_group_id,
                    (PromotionalScheme.item_id.is_(None) & PromotionalScheme.item_group_id.is_(None))),
                or_(PromotionalScheme.valid_from.is_(None), PromotionalScheme.valid_from <= on_date),
                or_(PromotionalScheme.valid_to.is_(None), PromotionalScheme.valid_to >= on_date),
            ).order_by(PromotionalScheme.scheme_id))).all()
            promotion = promotions[0] if len(promotions) == 1 else None
            if len(promotions) > 1:
                raise ValueError("Multiple promotions match this line; a single deterministic promotion is required.")
            if promotion and promotion.scheme_type == "DISCOUNT":
                promo_discount = pre_discount * Decimal(promotion.discount_value) / Decimal("100") if promotion.discount_type == "PERCENT" else Decimal(promotion.discount_value)
                discount = min(_money(pre_discount), discount + _money(promo_discount))
            stock_quantity = (line.quantity * factor).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
            total_weight += line.quantity * Decimal(item.weight_per_unit)
            calculations.append(CalculatedLine(
                item_id=line.item_id, price_list_id=selected_list_id, entered_quantity=line.quantity, uom_id=line.uom_id,
                conversion_factor=factor, stock_quantity=stock_quantity, base_rate=_money(rate),
                price_list_rate=_money(Decimal(item_price.rate) if item_price else rate),
                item_price_id=item_price.item_price_id if item_price else None,
                pricing_rule_id=rule.pricing_rule_id if rule else None,
                promotion_id=promotion.scheme_id if promotion else None,
                discount_amount=discount, line_total=_money(pre_discount - discount),
            ))
            if promotion and promotion.scheme_type == "BUY_X_GET_Y":
                earned_sets = (line.quantity / Decimal(promotion.buy_quantity)).to_integral_value(rounding=ROUND_FLOOR)
                free_qty = earned_sets * Decimal(promotion.free_quantity)
                free_item = await session.scalar(select(Item).where(
                    Item.tenant_id == tenant_id,
                    Item.item_id == promotion.free_item_id,
                    Item.is_active.is_(True),
                    (Item.is_purchase_item.is_(True) if context == "BUYING" else Item.is_sales_item.is_(True)),
                )) if free_qty > 0 else None
                if free_qty > 0 and free_item is None:
                    raise ValueError("Eligible buy-x-get-y promotion has no active tenant-owned free sales item.")
                if free_item:
                    total_weight += free_qty * Decimal(free_item.weight_per_unit)
                    calculations.append(CalculatedLine(
                        item_id=free_item.item_id, price_list_id=selected_list_id, entered_quantity=free_qty, uom_id=None,
                        conversion_factor=Decimal("1"), stock_quantity=free_qty,
                        base_rate=Decimal("0"), price_list_rate=Decimal("0"), item_price_id=None,
                        pricing_rule_id=None, promotion_id=promotion.scheme_id,
                        discount_amount=Decimal("0"), line_total=Decimal("0"), is_free=True,
                    ))
        subtotal = sum((line.line_total for line in calculations), Decimal("0"))
        shipping_charge = await self._shipping_charge(
            session, tenant_id, shipping_rule_id, destination_country, destination_state,
            subtotal, sum((line.entered_quantity for line in calculations), Decimal("0")), total_weight,
        )
        canonical = {
            "context": context, "currency": currency, "price_list_id": str(price_list_id) if price_list_id else None,
            "lines": [{**asdict(line), "item_id": str(line.item_id), "uom_id": str(line.uom_id) if line.uom_id else None,
                       "item_price_id": str(line.item_price_id) if line.item_price_id else None,
                       "pricing_rule_id": str(line.pricing_rule_id) if line.pricing_rule_id else None,
                       "promotion_id": str(line.promotion_id) if line.promotion_id else None} for line in calculations],
            "shipping_charge": str(shipping_charge),
        }
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
        return CalculationResult(
            context=context, currency=currency, price_list_id=price_list_id, lines=tuple(calculations),
            subtotal=_money(subtotal), discount_total=_money(sum((line.discount_amount for line in calculations), Decimal("0"))),
            shipping_charge=shipping_charge, total=_money(subtotal + shipping_charge),
            warnings=tuple(warnings), calculation_hash=digest,
        )

    async def _shipping_charge(
        self, session: AsyncSession, tenant_id: uuid.UUID, rule_id: uuid.UUID | None,
        country: str | None, state: str | None, subtotal: Decimal, total_quantity: Decimal,
        total_weight: Decimal,
    ) -> Decimal:
        if rule_id is None:
            return Decimal("0.0000")
        rule = await session.scalar(select(ShippingRule).where(
            ShippingRule.tenant_id == tenant_id, ShippingRule.shipping_rule_id == rule_id,
            ShippingRule.is_active.is_(True),
        ))
        if rule is None:
            raise ValueError("Shipping rule must be active and belong to this workspace.")
        if rule.destination_country and rule.destination_country.casefold() != (country or "").casefold():
            raise ValueError("Selected shipping rule does not match the destination country.")
        if rule.destination_state and rule.destination_state.casefold() != (state or "").casefold():
            raise ValueError("Selected shipping rule does not match the destination state.")
        conditions = (await session.scalars(select(ShippingRuleCondition).where(
            ShippingRuleCondition.tenant_id == tenant_id,
            ShippingRuleCondition.shipping_rule_id == rule_id,
        ).order_by(ShippingRuleCondition.condition_id))).all()
        charge = Decimal("0")
        for condition in conditions:
            base = subtotal if condition.based_on == "ORDER_VALUE" else total_quantity if condition.based_on == "ITEM_QTY" else total_weight
            if condition.min_value is not None and base < condition.min_value:
                continue
            if condition.max_value is not None and base > condition.max_value:
                continue
            if condition.charge_type == "FIXED":
                amount = Decimal(condition.rate)
            elif condition.charge_type == "PER_UNIT":
                amount = Decimal(condition.rate) * base
            else:
                amount = subtotal * Decimal(condition.rate) / Decimal("100")
            charge += amount
        return _money(charge)


commercial_calculation_service = CommercialCalculationService()
