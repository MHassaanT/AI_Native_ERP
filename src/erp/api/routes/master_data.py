"""Tenant-scoped CRUD API for shared ERP master data."""

import uuid
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, select, update
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models import (
    Address, Contact, Item, ItemGroup, ItemPrice, IssueType, NamingSeries,
    PriceList, ProductBundle, ProductBundleItem, TermsAndConditionsTemplate,
    UOM, UOMConversion, Tenant,
)
from erp.db.models.phase_b import (
    ItemManufacturer, LoyaltyPointEntry, LoyaltyProgram, PricingRule, PromotionalScheme,
    PurchaseTaxesAndChargesTemplate, PurchaseTaxesAndChargesTemplateDetail, SalesPartner,
    SalesTeam, ShippingRule, ShippingRuleCondition, SupplierGroup,
)
from erp.db.models.onboarding import TenantSettings


router = APIRouter(prefix="/master-data", tags=["Shared Master Data"])

RESOURCES = {
    "item-groups": (ItemGroup, "item_group_id", "group_name"),
    "price-lists": (PriceList, "price_list_id", "price_list_name"),
    "item-prices": (ItemPrice, "item_price_id", "item_price_id"),
    "contacts": (Contact, "contact_id", "full_name"),
    "addresses": (Address, "address_id", "address_title"),
    "uoms": (UOM, "uom_id", "uom_name"),
    "uom-conversions": (UOMConversion, "conversion_id", "conversion_id"),
    "naming-series": (NamingSeries, "naming_series_id", "document_type"),
    "terms-templates": (TermsAndConditionsTemplate, "terms_template_id", "template_name"),
    "product-bundles": (ProductBundle, "bundle_id", "bundle_name"),
    "product-bundle-items": (ProductBundleItem, "bundle_line_id", "bundle_line_id"),
    "issue-types": (IssueType, "issue_type_id", "type_name"),
    "supplier-groups": (SupplierGroup, "supplier_group_id", "group_name"),
    "purchase-tax-templates": (PurchaseTaxesAndChargesTemplate, "template_id", "title"),
    "purchase-tax-details": (PurchaseTaxesAndChargesTemplateDetail, "detail_id", "description"),
    "shipping-rules": (ShippingRule, "shipping_rule_id", "rule_name"),
    "shipping-conditions": (ShippingRuleCondition, "condition_id", "condition_id"),
    "item-manufacturers": (ItemManufacturer, "item_manufacturer_id", "manufacturer_name"),
    "promotional-schemes": (PromotionalScheme, "scheme_id", "scheme_name"),
    "pricing-rules": (PricingRule, "pricing_rule_id", "rule_name"),
    "sales-partners": (SalesPartner, "sales_partner_id", "partner_name"),
    "sales-teams": (SalesTeam, "sales_team_id", "sales_team_id"),
    "loyalty-programs": (LoyaltyProgram, "loyalty_program_id", "program_name"),
}

class MasterDataPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


def _resource(name: str):
    try:
        return RESOURCES[name]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown master data resource.") from exc


def _coerce(model: type, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {column.key: column for column in inspect(model).columns}
    result = {}
    for key, value in payload.items():
        if key not in allowed or key in {"tenant_id", "created_at", "updated_at"}:
            raise HTTPException(status_code=422, detail=f"Field '{key}' cannot be set.")
        if value is not None and isinstance(allowed[key].type, PGUUID) and not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(str(value))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Field '{key}' must be a UUID.") from exc
        if value is not None and key in {"valid_from", "valid_to"} and isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Field '{key}' must be an ISO date.") from exc
        if value is not None and isinstance(allowed[key].type, Numeric):
            try:
                value = Decimal(str(value))
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Field '{key}' must be numeric.") from exc
        result[key] = value
    return result

REFERENCE_CHECKS = {
    ItemGroup: {"parent_id": (ItemGroup, "item_group_id")},
    ItemPrice: {"item_id": (Item, "item_id"), "price_list_id": (PriceList, "price_list_id")},
    UOMConversion: {"from_uom_id": (UOM, "uom_id"), "to_uom_id": (UOM, "uom_id"), "item_id": (Item, "item_id")},
    ProductBundle: {"bundle_item_id": (Item, "item_id")},
    ProductBundleItem: {"bundle_id": (ProductBundle, "bundle_id"), "item_id": (Item, "item_id")},
    SupplierGroup: {"parent_id": (SupplierGroup, "supplier_group_id")},
    PurchaseTaxesAndChargesTemplateDetail: {"template_id": (PurchaseTaxesAndChargesTemplate, "template_id")},
    ShippingRuleCondition: {"shipping_rule_id": (ShippingRule, "shipping_rule_id")},
    ItemManufacturer: {"item_id": (Item, "item_id")},
    PromotionalScheme: {"item_id": (Item, "item_id"), "item_group_id": (ItemGroup, "item_group_id")},
    PricingRule: {"item_id": (Item, "item_id"), "item_group_id": (ItemGroup, "item_group_id"), "price_list_id": (PriceList, "price_list_id")},
    SalesTeam: {"sales_partner_id": (SalesPartner, "sales_partner_id")},
}

async def _check_references(session, tenant_id, model, values):
    for field, (ref_model, ref_key) in REFERENCE_CHECKS.get(model, {}).items():
        ref_id = values.get(field)
        if ref_id is None:
            continue
        exists = await session.scalar(select(getattr(ref_model, ref_key)).where(
            getattr(ref_model, ref_key) == ref_id, ref_model.tenant_id == tenant_id
        ).limit(1))
        if not exists:
            raise HTTPException(status_code=422, detail=f"{field} must reference a record in this workspace.")

async def _rebuild_item_tree(session, tenant_id):
    groups = list((await session.scalars(select(ItemGroup).where(ItemGroup.tenant_id == tenant_id))).all())
    by_parent: dict[uuid.UUID | None, list[ItemGroup]] = {}
    for group in groups:
        by_parent.setdefault(group.parent_id, []).append(group)
    for siblings in by_parent.values():
        siblings.sort(key=lambda row: row.group_name.casefold())
    counter = 1
    visited: set[uuid.UUID] = set()
    def visit(node):
        nonlocal counter
        if node.item_group_id in visited:
            raise HTTPException(status_code=422, detail="Item group hierarchy contains a cycle.")
        visited.add(node.item_group_id)
        node.lft = counter
        counter += 1
        for child in by_parent.get(node.item_group_id, []):
            visit(child)
        node.rgt = counter
        counter += 1
    for root in by_parent.get(None, []):
        visit(root)
    if len(visited) != len(groups):
        raise HTTPException(status_code=422, detail="Item group hierarchy contains an unreachable cycle.")

async def _rebuild_supplier_tree(session, tenant_id):
    groups = list((await session.scalars(select(SupplierGroup).where(SupplierGroup.tenant_id == tenant_id))).all())
    children: dict[uuid.UUID | None, list[SupplierGroup]] = {}
    for group in groups: children.setdefault(group.parent_id, []).append(group)
    for siblings in children.values(): siblings.sort(key=lambda row: row.group_name.casefold())
    count = 1
    seen: set[uuid.UUID] = set()
    def visit(node):
        nonlocal count
        if node.supplier_group_id in seen: raise HTTPException(status_code=422, detail="Supplier group hierarchy contains a cycle.")
        seen.add(node.supplier_group_id); node.lft = count; count += 1
        for child in children.get(node.supplier_group_id, []): visit(child)
        node.rgt = count; count += 1
    for root in children.get(None, []): visit(root)
    if len(seen) != len(groups): raise HTTPException(status_code=422, detail="Supplier group hierarchy contains an unreachable cycle.")

@router.get("")
async def list_resources():
    """Lists supported resource names and their entity counts for UI discovery."""
    return [{"resource": key, "label": key.replace("-", " ").title()} for key in RESOURCES]

@router.post("/defaults", status_code=status.HTTP_200_OK)
async def seed_defaults(session: DbSessionDep, tenant_id: TenantIdDep):
    """Idempotently provisions a small starter catalog for this tenant."""
    created = {"uoms": [], "item_groups": [], "price_lists": [], "issue_types": []}
    for name, abbreviation in [("Each", "ea"), ("Kilogram", "kg"), ("Gram", "g"), ("Litre", "L"), ("Metre", "m"), ("Hour", "h"), ("Box", "box")]:
        found = await session.scalar(select(UOM.uom_id).where(UOM.tenant_id == tenant_id, UOM.uom_name == name))
        if not found:
            row = UOM(tenant_id=tenant_id, uom_name=name, abbreviation=abbreviation)
            session.add(row); created["uoms"].append(name)
    root = await session.scalar(select(ItemGroup).where(ItemGroup.tenant_id == tenant_id, ItemGroup.group_name == "All Item Groups"))
    if root is None:
        root = ItemGroup(tenant_id=tenant_id, group_name="All Item Groups", is_group=True)
        session.add(root)
        await session.flush()
        created["item_groups"].append(root.group_name)
    for name in ["Products", "Raw Materials", "Services"]:
        found = await session.scalar(select(ItemGroup.item_group_id).where(ItemGroup.tenant_id == tenant_id, ItemGroup.group_name == name))
        if not found:
            session.add(ItemGroup(tenant_id=tenant_id, group_name=name, parent_id=root.item_group_id, is_group=False))
            created["item_groups"].append(name)
    tenant_currency = await session.scalar(select(Tenant.currency).where(Tenant.tenant_id == tenant_id)) or "USD"
    for name, currency, selling, buying in [("Standard Selling", tenant_currency, True, False), ("Standard Buying", tenant_currency, False, True)]:
        found = await session.scalar(select(PriceList.price_list_id).where(PriceList.tenant_id == tenant_id, PriceList.price_list_name == name))
        if not found:
            session.add(PriceList(tenant_id=tenant_id, price_list_name=name, currency=currency, selling=selling, buying=buying)); created["price_lists"].append(name)
    for name in ["Bug", "Feature Request", "Question", "Other"]:
        found = await session.scalar(select(IssueType.issue_type_id).where(IssueType.tenant_id == tenant_id, IssueType.type_name == name))
        if not found:
            session.add(IssueType(tenant_id=tenant_id, type_name=name)); created["issue_types"].append(name)
    await session.flush()
    await _rebuild_item_tree(session, tenant_id)
    return {"created": created, "message": "Default master data is ready; existing records were preserved."}

@router.get("/{resource}")
async def list_resource(resource: str, session: DbSessionDep, tenant_id: TenantIdDep):
    model, _, sort_key = _resource(resource)
    rows = (await session.scalars(select(model).where(model.tenant_id == tenant_id).order_by(getattr(model, sort_key)))).all()
    return list(rows)

@router.post("/{resource}", status_code=status.HTTP_201_CREATED)
async def create_resource(resource: str, payload: MasterDataPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    model, pk, _ = _resource(resource)
    values = _coerce(model, payload.data)
    await _check_references(session, tenant_id, model, values)
    if model is ItemPrice and values.get("valid_from") and values.get("valid_to") and values["valid_from"] > values["valid_to"]:
        raise HTTPException(status_code=422, detail="valid_from must be on or before valid_to.")
    if model in {ItemGroup, SupplierGroup} and values.get("parent_id"):
        group_model, group_pk = (ItemGroup, "item_group_id") if model is ItemGroup else (SupplierGroup, "supplier_group_id")
        parent = await session.scalar(select(group_model).where(getattr(group_model, group_pk) == values["parent_id"], group_model.tenant_id == tenant_id))
        if parent and not parent.is_group:
            raise HTTPException(status_code=422, detail="Only group nodes can contain child groups.")
    if model is SalesTeam:
        from sqlalchemy import func
        total = await session.scalar(select(func.coalesce(func.sum(SalesTeam.contribution_pct), 0)).where(SalesTeam.tenant_id == tenant_id, SalesTeam.document_type == values.get("document_type"), SalesTeam.document_id == values.get("document_id")))
        if Decimal(str(total or 0)) + Decimal(str(values.get("contribution_pct", 100))) > Decimal("100"):
            raise HTTPException(status_code=422, detail="Sales team contribution percentages cannot total more than 100%.")
    row = model(tenant_id=tenant_id, **values)
    session.add(row)
    try:
        await session.flush()
        if model is ItemGroup:
            await _rebuild_item_tree(session, tenant_id)
            await session.flush()
        elif model is SupplierGroup:
            await _rebuild_supplier_tree(session, tenant_id)
            await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A conflicting or invalid master data record already exists.") from exc
    return row

@router.get("/{resource}/{record_id}")
async def get_resource(resource: str, record_id: uuid.UUID, session: DbSessionDep, tenant_id: TenantIdDep):
    model, pk, _ = _resource(resource)
    row = await session.scalar(select(model).where(getattr(model, pk) == record_id, model.tenant_id == tenant_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Master data record not found.")
    return row

@router.patch("/{resource}/{record_id}")
async def update_resource(resource: str, record_id: uuid.UUID, payload: MasterDataPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    model, pk, _ = _resource(resource)
    row = await session.scalar(select(model).where(getattr(model, pk) == record_id, model.tenant_id == tenant_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Master data record not found.")
    values = _coerce(model, payload.data)
    await _check_references(session, tenant_id, model, values)
    if model in {ItemGroup, SupplierGroup} and "parent_id" in values and values["parent_id"] == record_id:
        raise HTTPException(status_code=422, detail="A group cannot be its own parent.")
    if model is ItemPrice:
        start = values.get("valid_from", row.valid_from)
        end = values.get("valid_to", row.valid_to)
        if start and end and start > end:
            raise HTTPException(status_code=422, detail="valid_from must be on or before valid_to.")
    if model in {ItemGroup, SupplierGroup} and values.get("parent_id"):
        group_model, group_pk = (ItemGroup, "item_group_id") if model is ItemGroup else (SupplierGroup, "supplier_group_id")
        parent = await session.scalar(select(group_model).where(getattr(group_model, group_pk) == values["parent_id"], group_model.tenant_id == tenant_id))
        if parent and not parent.is_group:
            raise HTTPException(status_code=422, detail="Only group nodes can contain child groups.")
    if model in {ItemGroup, SupplierGroup} and values.get("is_group") is False:
        group_pk = "item_group_id" if model is ItemGroup else "supplier_group_id"
        has_children = await session.scalar(select(getattr(model, group_pk)).where(model.parent_id == record_id, model.tenant_id == tenant_id).limit(1))
        if has_children:
            raise HTTPException(status_code=409, detail="A group with child groups cannot be changed to a leaf group.")
    if model is SalesTeam and "contribution_pct" in values:
        from sqlalchemy import func
        total = await session.scalar(select(func.coalesce(func.sum(SalesTeam.contribution_pct), 0)).where(SalesTeam.tenant_id == tenant_id, SalesTeam.document_type == row.document_type, SalesTeam.document_id == row.document_id, SalesTeam.sales_team_id != row.sales_team_id))
        if Decimal(str(total or 0)) + Decimal(str(values["contribution_pct"])) > Decimal("100"):
            raise HTTPException(status_code=422, detail="Sales team contribution percentages cannot total more than 100%.")
    for key, value in values.items():
        setattr(row, key, value)
    try:
        await session.flush()
        if model is ItemGroup:
            await _rebuild_item_tree(session, tenant_id)
            await session.flush()
        elif model is SupplierGroup:
            await _rebuild_supplier_tree(session, tenant_id)
            await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A conflicting or invalid master data record already exists.") from exc
    return row

@router.delete("/{resource}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(resource: str, record_id: uuid.UUID, session: DbSessionDep, tenant_id: TenantIdDep):
    model, pk, _ = _resource(resource)
    row = await session.scalar(select(model).where(getattr(model, pk) == record_id, model.tenant_id == tenant_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Master data record not found.")
    await session.delete(row)
    try:
        await session.flush()
        if model is ItemGroup:
            await _rebuild_item_tree(session, tenant_id)
            await session.flush()
        elif model is SupplierGroup:
            await _rebuild_supplier_tree(session, tenant_id)
            await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This record is referenced by other data and cannot be deleted.") from exc

@router.post("/naming-series/{series_id}/next-number")
async def next_number(series_id: uuid.UUID, session: DbSessionDep, tenant_id: TenantIdDep):
    """Atomically reserves and returns the next formatted document number."""
    model = NamingSeries
    result = await session.execute(
        update(model).where(model.naming_series_id == series_id, model.tenant_id == tenant_id, model.is_active.is_(True))
        .values(current_number=model.current_number + 1).returning(model.prefix, model.current_number, model.number_width)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Active naming series not found.")
    prefix, number, width = row
    return {"number": f"{prefix}{number:0{width}d}", "current_number": number}

class OperationalSettingsPayload(BaseModel):
    auto_material_request: bool | None = None
    allow_negative_stock: bool | None = None
    over_receipt_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    over_billing_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    backflush_based_on: str | None = Field(default=None, pattern="^(BOM|TRANSFER)$")
    valuation_method: str | None = Field(default=None, pattern="^(FIFO|MOVING_AVERAGE|STANDARD)$")
    stock_uom: str | None = None
    default_warehouse_id: uuid.UUID | None = None
    default_buying_price_list: str | None = None
    default_selling_price_list: str | None = None


@router.get("/settings/operational/current")
async def get_operational_settings(session: DbSessionDep, tenant_id: TenantIdDep):
    settings = await session.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
    if settings is None:
        settings = TenantSettings(tenant_id=tenant_id)
        session.add(settings)
        await session.flush()
    return settings


@router.patch("/settings/operational/current")
async def update_operational_settings(payload: OperationalSettingsPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    settings = await session.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
    if settings is None:
        settings = TenantSettings(tenant_id=tenant_id)
        session.add(settings)
    values = payload.model_dump(exclude_unset=True)
    for key, is_buying in (("default_buying_price_list", True), ("default_selling_price_list", False)):
        list_name = values.get(key)
        if list_name:
            context_filter = PriceList.buying.is_(True) if is_buying else PriceList.selling.is_(True)
            price_list = await session.scalar(select(PriceList.price_list_id).where(
                PriceList.tenant_id == tenant_id,
                PriceList.price_list_name == list_name,
                PriceList.is_active.is_(True),
                context_filter,
            ))
            if not price_list:
                context = "buying" if is_buying else "selling"
                raise HTTPException(status_code=422, detail=f"Default {context} price list must be active and configured for that context in this workspace.")
    if values.get("default_warehouse_id"):
        from erp.db.models.inventory import Warehouse
        warehouse = await session.scalar(select(Warehouse.warehouse_id).where(Warehouse.warehouse_id == values["default_warehouse_id"], Warehouse.tenant_id == tenant_id))
        if not warehouse:
            raise HTTPException(status_code=422, detail="Default warehouse must belong to this workspace.")
    for key, value in values.items():
        setattr(settings, key, value)
    await session.flush()
    return settings


class ShippingQuotePayload(BaseModel):
    destination_country: str
    destination_state: str | None = None
    order_value: Decimal = Field(ge=0)
    weight: Decimal = Field(default=Decimal("0"), ge=0)
    item_qty: Decimal = Field(default=Decimal("1"), ge=0)


@router.post("/shipping/quote")
async def quote_shipping(payload: ShippingQuotePayload, session: DbSessionDep, tenant_id: TenantIdDep):
    rules = (await session.scalars(select(ShippingRule).where(ShippingRule.tenant_id == tenant_id, ShippingRule.is_active.is_(True)).order_by(ShippingRule.priority.asc()))).all()
    rule_ids = [rule.shipping_rule_id for rule in rules if (not rule.destination_country or rule.destination_country.casefold() == payload.destination_country.casefold()) and (not rule.destination_state or rule.destination_state.casefold() == (payload.destination_state or "").casefold())]
    if not rule_ids:
        return {"matched": False, "shipping_charge": Decimal("0.0000")}
    conditions = (await session.scalars(select(ShippingRuleCondition).where(ShippingRuleCondition.tenant_id == tenant_id, ShippingRuleCondition.shipping_rule_id.in_(rule_ids)))).all()
    values = {"ORDER_VALUE": payload.order_value, "WEIGHT": payload.weight, "ITEM_QTY": payload.item_qty}
    rule_by_id = {rule.shipping_rule_id: rule for rule in rules}
    for rule_id in rule_ids:
        applicable = [c for c in conditions if c.shipping_rule_id == rule_id and (c.min_value is None or values[c.based_on] >= c.min_value) and (c.max_value is None or values[c.based_on] <= c.max_value)]
        if not applicable:
            continue
        condition = sorted(applicable, key=lambda c: (c.min_value or Decimal("0"), c.created_at), reverse=True)[0]
        base = values[condition.based_on]
        charge = condition.rate if condition.charge_type == "FIXED" else condition.rate * base if condition.charge_type == "PER_UNIT" else payload.order_value * condition.rate / Decimal("100")
        return {"matched": True, "rule_id": rule_id, "rule_name": rule_by_id[rule_id].rule_name, "shipping_charge": charge.quantize(Decimal("0.0001")), "based_on": condition.based_on}
    return {"matched": False, "shipping_charge": Decimal("0.0000")}


class PriceEvaluationPayload(BaseModel):
    item_id: uuid.UUID
    price_list_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    as_of_date: date | None = None
    unit_rate: Decimal = Field(default=Decimal("0"), ge=0)


@router.post("/pricing/evaluate")
async def evaluate_pricing(payload: PriceEvaluationPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    from sqlalchemy import or_
    from erp.db.models.shared_master import ItemPrice
    item = await session.scalar(select(Item).where(Item.item_id == payload.item_id, Item.tenant_id == tenant_id))
    price_list = await session.scalar(select(PriceList).where(PriceList.price_list_id == payload.price_list_id, PriceList.tenant_id == tenant_id, PriceList.is_active.is_(True)))
    if not item or not price_list:
        raise HTTPException(status_code=404, detail="Item or active price list not found in this workspace.")
    as_of = payload.as_of_date or date.today()
    price = await session.scalar(select(ItemPrice).where(ItemPrice.tenant_id == tenant_id, ItemPrice.item_id == item.item_id, ItemPrice.price_list_id == price_list.price_list_id, or_(ItemPrice.valid_from.is_(None), ItemPrice.valid_from <= as_of), or_(ItemPrice.valid_to.is_(None), ItemPrice.valid_to >= as_of)).order_by(ItemPrice.valid_from.desc().nullslast()).limit(1))
    base = price.rate if price else item.standard_rate
    rules = (await session.scalars(
        select(PricingRule).where(
            PricingRule.tenant_id == tenant_id,
            PricingRule.is_active.is_(True),
            PricingRule.min_quantity <= payload.quantity,
            or_(PricingRule.item_id.is_(None), PricingRule.item_id == item.item_id),
            or_(PricingRule.item_group_id.is_(None), PricingRule.item_group_id == item.item_group_id),
            or_(PricingRule.price_list_id.is_(None), PricingRule.price_list_id == price_list.price_list_id),
            or_(PricingRule.valid_from.is_(None), PricingRule.valid_from <= as_of),
            or_(PricingRule.valid_to.is_(None), PricingRule.valid_to >= as_of),
        ).order_by(PricingRule.priority.asc())
    )).all()
    if not rules:
        return {"base_rate": base, "unit_rate": base, "matched_rule": None, "quantity": payload.quantity}
    rule = rules[0]
    discount = base * rule.discount_value / Decimal("100") if rule.discount_type == "PERCENT" else rule.discount_value
    unit_rate = max(Decimal("0"), base - discount)
    return {"base_rate": base, "unit_rate": unit_rate.quantize(Decimal("0.0001")), "matched_rule": rule.rule_name, "discount_type": rule.discount_type, "discount_value": rule.discount_value, "quantity": payload.quantity}


class LoyaltyEarnPayload(BaseModel):
    loyalty_program_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: uuid.UUID
    remarks: str | None = None


class LoyaltyRedeemPayload(BaseModel):
    loyalty_program_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    points: Decimal = Field(gt=0)
    remarks: str | None = None


async def _loyalty_balance(session, tenant_id, program_id, customer_id):
    from sqlalchemy import case, func
    balance = await session.scalar(select(func.coalesce(func.sum(case((LoyaltyPointEntry.entry_type == "EARN", LoyaltyPointEntry.points), else_=-LoyaltyPointEntry.points)), 0)).where(LoyaltyPointEntry.tenant_id == tenant_id, LoyaltyPointEntry.loyalty_program_id == program_id, LoyaltyPointEntry.customer_id == customer_id))
    return Decimal(str(balance or 0))


@router.get("/loyalty/balance/current")
async def loyalty_balance(session: DbSessionDep, tenant_id: TenantIdDep, loyalty_program_id: uuid.UUID, customer_id: uuid.UUID):
    from erp.db.models.sales import Customer
    program = await session.scalar(select(LoyaltyProgram).where(LoyaltyProgram.loyalty_program_id == loyalty_program_id, LoyaltyProgram.tenant_id == tenant_id))
    customer = await session.scalar(select(Customer.customer_id).where(Customer.customer_id == customer_id, Customer.tenant_id == tenant_id))
    if not program or not customer:
        raise HTTPException(status_code=404, detail="Program or customer not found.")
    return {"balance": await _loyalty_balance(session, tenant_id, loyalty_program_id, customer_id)}


@router.post("/loyalty/earn", status_code=status.HTTP_201_CREATED)
async def earn_loyalty_points(payload: LoyaltyEarnPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    from erp.db.models.sales import Customer, SalesInvoice
    program = await session.scalar(select(LoyaltyProgram).where(LoyaltyProgram.loyalty_program_id == payload.loyalty_program_id, LoyaltyProgram.tenant_id == tenant_id, LoyaltyProgram.is_active.is_(True)))
    customer = await session.scalar(select(Customer).where(Customer.customer_id == payload.customer_id, Customer.tenant_id == tenant_id, Customer.is_active.is_(True)).with_for_update())
    if not program or not customer:
        raise HTTPException(status_code=404, detail="Active program or customer not found.")
    invoice = await session.scalar(select(SalesInvoice).where(
        SalesInvoice.invoice_id == payload.invoice_id,
        SalesInvoice.tenant_id == tenant_id,
        SalesInvoice.customer_id == customer.customer_id,
        SalesInvoice.status.in_(("ISSUED", "PAID")),
    ).with_for_update())
    if invoice is None:
        raise HTTPException(status_code=422, detail="Select a non-cancelled invoice belonging to this customer and workspace.")
    tenant_currency = await session.scalar(select(Tenant.currency).where(Tenant.tenant_id == tenant_id))
    if invoice.currency.upper() != (tenant_currency or "USD").upper():
        raise HTTPException(status_code=422, detail="Invoice currency must match the workspace currency to earn loyalty points.")
    prior = await session.scalar(select(LoyaltyPointEntry).where(LoyaltyPointEntry.tenant_id == tenant_id, LoyaltyPointEntry.loyalty_program_id == program.loyalty_program_id, LoyaltyPointEntry.customer_id == customer.customer_id, LoyaltyPointEntry.invoice_id == invoice.invoice_id, LoyaltyPointEntry.entry_type == "EARN"))
    if prior:
        return {"entry": prior, "balance": await _loyalty_balance(session, tenant_id, program.loyalty_program_id, customer.customer_id), "idempotent_replay": True}
    points = (invoice.subtotal * program.points_per_currency).quantize(Decimal("0.0001"))
    if points <= 0:
        raise HTTPException(status_code=422, detail="Eligible amount produced no loyalty points.")
    entry = LoyaltyPointEntry(tenant_id=tenant_id, loyalty_program_id=program.loyalty_program_id, customer_id=customer.customer_id, invoice_id=payload.invoice_id, entry_type="EARN", points=points, remarks=payload.remarks)
    session.add(entry)
    await session.flush()
    return {"entry": entry, "balance": await _loyalty_balance(session, tenant_id, program.loyalty_program_id, customer.customer_id)}


@router.post("/loyalty/redeem", status_code=status.HTTP_201_CREATED)
async def redeem_loyalty_points(payload: LoyaltyRedeemPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    from erp.db.models.sales import Customer
    program = await session.scalar(select(LoyaltyProgram).where(LoyaltyProgram.loyalty_program_id == payload.loyalty_program_id, LoyaltyProgram.tenant_id == tenant_id, LoyaltyProgram.is_active.is_(True)))
    customer = await session.scalar(select(Customer).where(Customer.customer_id == payload.customer_id, Customer.tenant_id == tenant_id, Customer.is_active.is_(True)).with_for_update())
    if not program or not customer:
        raise HTTPException(status_code=404, detail="Active program or customer not found.")
    if payload.points < program.minimum_redemption_points:
        raise HTTPException(status_code=422, detail="Requested redemption is below the program minimum.")
    if payload.invoice_id:
        prior = await session.scalar(select(LoyaltyPointEntry).where(LoyaltyPointEntry.tenant_id == tenant_id, LoyaltyPointEntry.loyalty_program_id == program.loyalty_program_id, LoyaltyPointEntry.customer_id == customer.customer_id, LoyaltyPointEntry.invoice_id == payload.invoice_id, LoyaltyPointEntry.entry_type == "REDEEM"))
        if prior:
            raise HTTPException(status_code=409, detail="This invoice already has a loyalty redemption entry.")
    balance = await _loyalty_balance(session, tenant_id, program.loyalty_program_id, customer.customer_id)
    if payload.points > balance:
        raise HTTPException(status_code=409, detail="Customer does not have enough loyalty points.")
    entry = LoyaltyPointEntry(tenant_id=tenant_id, loyalty_program_id=program.loyalty_program_id, customer_id=customer.customer_id, invoice_id=payload.invoice_id, entry_type="REDEEM", points=payload.points, remarks=payload.remarks)
    session.add(entry)
    await session.flush()
    return {"entry": entry, "balance": balance - payload.points, "credit_value": (payload.points * program.redemption_value_per_point).quantize(Decimal("0.0001"))}

class PurchaseTaxCalculationPayload(BaseModel):
    template_id: uuid.UUID
    net_total: Decimal = Field(ge=0)


@router.post("/purchase-taxes/calculate")
async def calculate_purchase_taxes(payload: PurchaseTaxCalculationPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    from sqlalchemy.orm import selectinload
    template = await session.scalar(select(PurchaseTaxesAndChargesTemplate).options(selectinload(PurchaseTaxesAndChargesTemplate.taxes)).where(PurchaseTaxesAndChargesTemplate.template_id == payload.template_id, PurchaseTaxesAndChargesTemplate.tenant_id == tenant_id, PurchaseTaxesAndChargesTemplate.disabled.is_(False)))
    if template is None:
        raise HTTPException(status_code=404, detail="Active purchase tax template not found.")
    amount = payload.net_total
    rows = []
    previous_row_amount = Decimal("0")
    for detail in sorted(template.taxes, key=lambda row: (row.row_id if row.row_id is not None else 0, row.created_at)):
        base = payload.net_total if detail.charge_type == "On Net Total" else previous_row_amount if detail.charge_type == "On Previous Row Amount" else Decimal("1")
        charge = detail.rate if detail.charge_type == "Actual" else base * detail.rate / Decimal("100")
        previous_row_amount = charge
        amount += charge
        rows.append({"description": detail.description, "account_head": detail.account_head, "charge_type": detail.charge_type, "rate": detail.rate, "amount": charge.quantize(Decimal("0.0001"))})
    return {"template_id": template.template_id, "net_total": payload.net_total, "tax_total": (amount - payload.net_total).quantize(Decimal("0.0001")), "grand_total": amount.quantize(Decimal("0.0001")), "rows": rows}

@router.post("/promotions/evaluate")
async def evaluate_promotions(payload: PriceEvaluationPayload, session: DbSessionDep, tenant_id: TenantIdDep):
    from sqlalchemy import or_
    item = await session.scalar(select(Item).where(Item.item_id == payload.item_id, Item.tenant_id == tenant_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found in this workspace.")
    today = payload.as_of_date or date.today()
    schemes = (await session.scalars(select(PromotionalScheme).where(PromotionalScheme.tenant_id == tenant_id, PromotionalScheme.is_active.is_(True), or_(PromotionalScheme.item_id.is_(None), PromotionalScheme.item_id == item.item_id), or_(PromotionalScheme.item_group_id.is_(None), PromotionalScheme.item_group_id == item.item_group_id), or_(PromotionalScheme.valid_from.is_(None), PromotionalScheme.valid_from <= today), or_(PromotionalScheme.valid_to.is_(None), PromotionalScheme.valid_to >= today)).order_by(PromotionalScheme.created_at.asc()))).all()
    if not schemes:
        return {"matched": False, "discount_amount": Decimal("0.0000"), "free_quantity": Decimal("0.0000")}
    scheme = schemes[0]
    discount = Decimal("0")
    free_quantity = Decimal("0")
    if scheme.scheme_type == "DISCOUNT":
        discount = payload.unit_rate * scheme.discount_value / Decimal("100") if scheme.discount_type == "PERCENT" else scheme.discount_value
    elif scheme.buy_quantity and scheme.buy_quantity > 0 and scheme.free_quantity:
        multiples = (payload.quantity / scheme.buy_quantity).to_integral_value(rounding=ROUND_FLOOR)
        free_quantity = multiples * scheme.free_quantity
    return {"matched": True, "scheme_id": scheme.scheme_id, "scheme_name": scheme.scheme_name, "scheme_type": scheme.scheme_type, "discount_type": scheme.discount_type, "discount_value": scheme.discount_value, "discount_amount_per_unit": discount.quantize(Decimal("0.0001")), "free_quantity": free_quantity.quantize(Decimal("0.0001"))}

@router.get("/sales-team/by-document/{document_type}/{document_id}")
async def list_document_sales_team(document_type: str, document_id: uuid.UUID, session: DbSessionDep, tenant_id: TenantIdDep):
    assignments = (await session.scalars(select(SalesTeam).where(SalesTeam.tenant_id == tenant_id, SalesTeam.document_type == document_type.upper(), SalesTeam.document_id == document_id))).all()
    result = []
    for assignment in assignments:
        partner = await session.scalar(select(SalesPartner).where(SalesPartner.sales_partner_id == assignment.sales_partner_id, SalesPartner.tenant_id == tenant_id))
        effective_rate = assignment.commission_rate if assignment.commission_rate is not None else (partner.commission_rate if partner else Decimal("0"))
        result.append({"sales_team_id": assignment.sales_team_id, "partner_id": assignment.sales_partner_id, "partner_name": partner.partner_name if partner else "", "contribution_pct": assignment.contribution_pct, "commission_rate": effective_rate})
    return result
