"""Inventory Replenishment and Dynamic ROP API Endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.supply_chain.replenishment import (
    ReplenishmentEvaluationResult,
    replenishment_coordinator,
)
from erp.supply_chain.rop_engine import ROPEvaluation, rop_engine

router = APIRouter(prefix="/inventory", tags=["Dynamic Inventory & Replenishment"])


class CreateItemRequest(BaseModel):
    item_code: str = Field(..., min_length=2, max_length=64)
    item_name: str = Field(..., min_length=2, max_length=255)
    stock_uom: str = "Nos"
    standard_rate: Decimal = Decimal("0.0000")
    reorder_level: Decimal = Decimal("100.0000")
    initial_qty: Decimal = Decimal("0.0000")
    is_stock_item: bool = True
    is_sales_item: bool = True
    is_purchase_item: bool = True


class StockAdjustmentRequest(BaseModel):
    item_id: uuid.UUID
    delta_qty: Decimal
    reason: str = "MANUAL_ADJUSTMENT"


class CalculateROPRequest(BaseModel):
    item_code: str
    daily_demand_mean: Decimal = Decimal("150.0000")
    daily_demand_std: Decimal = Decimal("25.0000")
    lead_time_mean_days: Decimal = Decimal("14.0000")
    lead_time_std_days: Decimal = Decimal("3.0000")


@router.get("/items", summary="List inventory items with stock levels")
async def list_inventory_items(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns items with on-hand and available quantities for the tenant."""
    stmt = (
        select(
            Item,
            StockLevel.current_qty,
            StockLevel.reserved_qty,
            StockLevel.available_qty,
            StockLevel.valuation_rate,
        )
        .outerjoin(
            StockLevel,
            (StockLevel.item_id == Item.item_id) & (StockLevel.tenant_id == Item.tenant_id),
        )
        .where(Item.tenant_id == tenant_id)
        .order_by(Item.item_code.asc())
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for item, curr_qty, res_qty, avail_qty, val_rate in rows:
        items.append(
            {
                "item_id": str(item.item_id),
                "item_code": item.item_code,
                "item_name": item.item_name,
                "stock_uom": item.stock_uom,
                "standard_rate": str(item.standard_rate),
                "reorder_level": str(item.reorder_level),
                "current_qty": str(curr_qty if curr_qty is not None else Decimal("0.0000")),
                "reserved_qty": str(res_qty if res_qty is not None else Decimal("0.0000")),
                "available_qty": str(avail_qty if avail_qty is not None else Decimal("0.0000")),
                "valuation_rate": str(val_rate if val_rate is not None else item.standard_rate),
                "is_active": item.is_active,
            }
        )
    return items


@router.post("/items", status_code=status.HTTP_201_CREATED, summary="Create inventory item")
async def create_inventory_item(req: CreateItemRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Registers a new item in the master catalog and creates initial stock entry."""
    existing = (
        await db.execute(
            select(Item).where(Item.tenant_id == tenant_id, Item.item_code == req.item_code)
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item with code '{req.item_code}' already exists.",
        )

    # Get default warehouse
    wh = (
        (await db.execute(select(Warehouse).where(Warehouse.tenant_id == tenant_id)))
        .scalars()
        .first()
    )
    if not wh:
        wh = Warehouse(
            tenant_id=tenant_id,
            warehouse_code="WH-MAIN-01",
            warehouse_name="Central Industrial Warehouse",
        )
        db.add(wh)
        await db.flush()

    item = Item(
        tenant_id=tenant_id,
        item_code=req.item_code,
        item_name=req.item_name,
        stock_uom=req.stock_uom,
        standard_rate=req.standard_rate,
        reorder_level=req.reorder_level,
        is_stock_item=req.is_stock_item,
        is_sales_item=req.is_sales_item,
        is_purchase_item=req.is_purchase_item,
        is_active=True,
    )
    db.add(item)
    await db.flush()

    stock = StockLevel(
        tenant_id=tenant_id,
        item_id=item.item_id,
        warehouse_id=wh.warehouse_id,
        current_qty=req.initial_qty,
        reserved_qty=Decimal("0.0000"),
        available_qty=req.initial_qty,
        valuation_rate=req.standard_rate,
    )
    db.add(stock)

    if req.initial_qty > 0:
        sle = StockLedgerEntry(
            tenant_id=tenant_id,
            posting_datetime=datetime.now(UTC),
            item_id=item.item_id,
            warehouse_id=wh.warehouse_id,
            actual_qty=req.initial_qty,
            qty_after_transaction=req.initial_qty,
            incoming_rate=req.standard_rate,
            valuation_rate=req.standard_rate,
            source_document_type="OPENING_STOCK",
            source_document_id=uuid.uuid4(),
        )
        db.add(sle)

    await db.flush()
    return item


@router.post("/stock-adjustment", summary="Adjust inventory stock level")
async def adjust_stock(req: StockAdjustmentRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Adjusts on-hand stock and appends immutable StockLedgerEntry."""
    stock = (
        await db.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == req.item_id,
            )
        )
    ).scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock level not found.")

    new_qty = stock.current_qty + req.delta_qty
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient inventory. Adjustment would result in negative stock ({new_qty}).",
        )

    stock.current_qty = new_qty
    stock.available_qty = new_qty - stock.reserved_qty

    sle = StockLedgerEntry(
        tenant_id=tenant_id,
        posting_datetime=datetime.now(UTC),
        item_id=req.item_id,
        warehouse_id=stock.warehouse_id,
        actual_qty=req.delta_qty,
        qty_after_transaction=new_qty,
        valuation_rate=stock.valuation_rate,
        source_document_type=req.reason,
        source_document_id=uuid.uuid4(),
    )
    db.add(sle)
    await db.flush()
    return {
        "status": "SUCCESS",
        "current_qty": str(new_qty),
        "available_qty": str(stock.available_qty),
    }


@router.post(
    "/calculate-rop",
    response_model=ROPEvaluation,
    summary="Calculate dynamic Reorder Point (ROP)",
)
async def calculate_dynamic_rop_endpoint(req: CalculateROPRequest):
    """Calculates stochastic ROP incorporating demand and lead-time distributions (Z=2.33)."""
    return rop_engine.calculate_rop(
        item_code=req.item_code,
        mu_d=req.daily_demand_mean,
        sigma_d=req.daily_demand_std,
        mu_l=req.lead_time_mean_days,
        sigma_l=req.lead_time_std_days,
    )


@router.post(
    "/replenish/{item_id}",
    response_model=ReplenishmentEvaluationResult,
    summary="Evaluate stock and trigger automated replenishment",
)
async def evaluate_and_replenish_endpoint(
    item_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Evaluates OnHand + OnOrder <= ROP. Autonomously generates Purchase Order if triggered."""
    try:
        return await replenishment_coordinator.evaluate_and_replenish_item(
            session=db,
            tenant_id=tenant_id,
            item_id=item_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
