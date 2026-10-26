"""Immutable Product Bundle expansion and stock requirement helpers."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item
from erp.db.models.shared_master import ProductBundle, ProductBundleItem
from erp.workflows.commercial.calculation_service import CommercialCalculationService


async def snapshot_bundle_components(
    session: AsyncSession, tenant_id: uuid.UUID, parent_item_id: uuid.UUID,
) -> list[dict[str, Any]] | None:
    """Return per-parent-unit stock/UOM snapshots, or None for an ordinary item."""
    bundle = await session.scalar(select(ProductBundle).where(
        ProductBundle.tenant_id == tenant_id,
        ProductBundle.bundle_item_id == parent_item_id,
        ProductBundle.is_active.is_(True),
    ))
    if bundle is None:
        return None
    components = (await session.scalars(select(ProductBundleItem).where(
        ProductBundleItem.tenant_id == tenant_id,
        ProductBundleItem.bundle_id == bundle.bundle_id,
    ).order_by(ProductBundleItem.bundle_line_id))).all()
    if not components:
        raise ValueError("An active product bundle must contain at least one component.")

    snapshot: list[dict[str, Any]] = []
    for component in components:
        item = await session.scalar(select(Item).where(
            Item.tenant_id == tenant_id,
            Item.item_id == component.item_id,
            Item.is_active.is_(True),
        ))
        if item is None:
            raise ValueError("Every product-bundle component must remain active in this workspace.")
        if not item.is_stock_item:
            raise ValueError("Product-bundle components must be stock items so reservation and returns can be reconciled.")
        nested_bundle = await session.scalar(select(ProductBundle.bundle_id).where(
            ProductBundle.tenant_id == tenant_id,
            ProductBundle.bundle_item_id == item.item_id,
            ProductBundle.is_active.is_(True),
        ))
        if nested_bundle is not None:
            raise ValueError("Nested product bundles are not supported; use one explicit component level.")
        factor = await CommercialCalculationService.resolve_uom_factor(
            session, tenant_id, item, component.uom_id,
        )
        quantity = Decimal(component.quantity)
        snapshot.append({
            "bundle_line_id": str(component.bundle_line_id),
            "item_id": str(item.item_id),
            "item_code": item.item_code,
            "item_name": item.item_name,
            "quantity_per_bundle": str(quantity),
            "uom_id": str(component.uom_id) if component.uom_id else None,
            "conversion_factor": str(factor),
            "stock_quantity_per_bundle": str(quantity * factor),
            "stock_uom": item.stock_uom,
        })
    return snapshot


def bundle_stock_requirements(snapshot: list[dict[str, Any]] | None, parent_quantity: Decimal) -> dict[uuid.UUID, Decimal]:
    """Aggregate required component stock quantities for a sold/delivered parent quantity."""
    requirements: dict[uuid.UUID, Decimal] = {}
    for component in snapshot or []:
        item_id = uuid.UUID(str(component["item_id"]))
        quantity = Decimal(str(component["stock_quantity_per_bundle"])) * parent_quantity
        requirements[item_id] = requirements.get(item_id, Decimal("0")) + quantity
    return requirements


def bundle_delivery_snapshot(
    snapshot: list[dict[str, Any]] | None,
    parent_quantity: Decimal,
    stock_rows: dict[uuid.UUID, Any],
) -> tuple[list[dict[str, Any]] | None, Decimal, Decimal]:
    """Scale an immutable bundle recipe to this delivery and freeze its stock cost."""
    if snapshot is None:
        return None, Decimal("0"), Decimal("0")
    delivery: list[dict[str, Any]] = []
    total_stock = Decimal("0")
    total_cost = Decimal("0")
    for component in snapshot:
        item_id = uuid.UUID(str(component["item_id"]))
        stock_quantity = Decimal(str(component["stock_quantity_per_bundle"])) * parent_quantity
        stock = stock_rows[item_id]
        rate = Decimal(stock.valuation_rate)
        cost_amount = stock_quantity * rate
        total_stock += stock_quantity
        total_cost += cost_amount
        delivery.append({
            **component,
            "quantity": str(Decimal(str(component["quantity_per_bundle"])) * parent_quantity),
            "stock_quantity": str(stock_quantity),
            "cost_unit_stock": str(rate),
            "cost_amount": str(cost_amount),
            "cost_valuation_method": "STOCK_LEVEL",
            "cost_is_estimated": False,
        })
    return delivery, total_stock, total_cost
