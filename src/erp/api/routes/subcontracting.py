"""Subcontracting Operations API (Orders, Material Transfers, Finished Goods Receipts)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.procurement.subcontracting_service import subcontracting_service

router = APIRouter(prefix="/subcontracting", tags=["Subcontracting Operations"])


class FinishedItemIn(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Decimal("0.0000")


class SuppliedItemIn(BaseModel):
    raw_item_id: uuid.UUID
    required_qty: Decimal = Field(gt=0)
    source_warehouse_id: Optional[uuid.UUID] = None
    supplier_warehouse_id: Optional[uuid.UUID] = None


class CreateSubcontractingOrderSchema(BaseModel):
    sco_number: str
    supplier_id: uuid.UUID
    order_date: Optional[date] = None
    service_cost: Decimal = Decimal("0.0000")
    po_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    finished_items: List[FinishedItemIn] = []
    supplied_items: List[SuppliedItemIn] = []


class TransferMaterialIn(BaseModel):
    raw_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    source_warehouse_id: uuid.UUID
    supplier_warehouse_id: uuid.UUID


class TransferMaterialsSchema(BaseModel):
    transfers: List[TransferMaterialIn]


class ReceiptItemIn(BaseModel):
    item_id: uuid.UUID
    quantity_received: Decimal = Field(gt=0)
    service_rate: Decimal = Decimal("0.0000")


class CreateReceiptSchema(BaseModel):
    scr_number: str
    sco_id: uuid.UUID
    target_warehouse_id: uuid.UUID
    finished_items_received: List[ReceiptItemIn]
    posting_date: Optional[date] = None


@router.post("/orders", status_code=status.HTTP_201_CREATED, summary="Create Subcontracting Order")
async def create_order(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: CreateSubcontractingOrderSchema,
) -> Dict[str, Any]:
    sco = await subcontracting_service.create_subcontracting_order(
        session=session,
        tenant_id=tenant_id,
        sco_number=payload.sco_number,
        supplier_id=payload.supplier_id,
        order_date=payload.order_date,
        service_cost=payload.service_cost,
        po_id=payload.po_id,
        notes=payload.notes,
        finished_items=[it.model_dump() for it in payload.finished_items],
        supplied_items=[it.model_dump() for it in payload.supplied_items],
    )
    return {
        "sco_id": str(sco.sco_id),
        "sco_number": sco.sco_number,
        "supplier_id": str(sco.supplier_id),
        "status": sco.status,
        "service_cost": sco.service_cost,
        "items_count": len(sco.items),
        "supplied_count": len(sco.supplied_items),
    }


@router.get("/orders", summary="List Subcontracting Orders")
async def list_orders(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    supplier_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    orders = await subcontracting_service.list_subcontracting_orders(
        session, tenant_id, supplier_id=supplier_id, status=status
    )
    return [
        {
            "sco_id": str(o.sco_id),
            "sco_number": o.sco_number,
            "supplier_id": str(o.supplier_id),
            "supplier_name": o.supplier.supplier_name if o.supplier else None,
            "order_date": o.order_date,
            "service_cost": o.service_cost,
            "status": o.status,
            "items": [
                {
                    "item_id": str(it.item_id),
                    "item_code": it.item.item_code if it.item else None,
                    "item_name": it.item.item_name if it.item else None,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "line_total": it.line_total,
                }
                for it in o.items
            ],
            "supplied_items": [
                {
                    "raw_item_id": str(s.raw_item_id),
                    "raw_item_code": s.raw_item.item_code if s.raw_item else None,
                    "required_qty": s.required_qty,
                    "supplied_qty": s.supplied_qty,
                    "consumed_qty": s.consumed_qty,
                }
                for s in o.supplied_items
            ],
        }
        for o in orders
    ]


@router.get("/orders/{sco_id}", summary="Get Subcontracting Order Details")
async def get_order(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    sco_id: uuid.UUID,
) -> Dict[str, Any]:
    o = await subcontracting_service.get_subcontracting_order(session, tenant_id, sco_id)
    if not o:
        raise HTTPException(status_code=404, detail="Subcontracting Order not found")
    return {
        "sco_id": str(o.sco_id),
        "sco_number": o.sco_number,
        "supplier_id": str(o.supplier_id),
        "supplier_name": o.supplier.supplier_name if o.supplier else None,
        "order_date": o.order_date,
        "service_cost": o.service_cost,
        "status": o.status,
        "notes": o.notes,
        "items": [
            {
                "item_id": str(it.item_id),
                "item_code": it.item.item_code if it.item else None,
                "item_name": it.item.item_name if it.item else None,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            }
            for it in o.items
        ],
        "supplied_items": [
            {
                "supplied_item_id": str(s.supplied_item_id),
                "raw_item_id": str(s.raw_item_id),
                "raw_item_code": s.raw_item.item_code if s.raw_item else None,
                "required_qty": s.required_qty,
                "supplied_qty": s.supplied_qty,
                "consumed_qty": s.consumed_qty,
                "source_warehouse_id": str(s.source_warehouse_id) if s.source_warehouse_id else None,
                "supplier_warehouse_id": str(s.supplier_warehouse_id) if s.supplier_warehouse_id else None,
            }
            for s in o.supplied_items
        ],
    }


@router.post("/orders/{sco_id}/submit", summary="Submit Subcontracting Order")
async def submit_order(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    sco_id: uuid.UUID,
) -> Dict[str, Any]:
    try:
        sco = await subcontracting_service.submit_subcontracting_order(session, tenant_id, sco_id)
        return {"sco_id": str(sco.sco_id), "status": sco.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{sco_id}/transfer", summary="Transfer Materials to Subcontractor")
async def transfer_materials(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    sco_id: uuid.UUID,
    payload: TransferMaterialsSchema,
) -> Dict[str, Any]:
    try:
        sco = await subcontracting_service.transfer_subcontracting_materials(
            session=session,
            tenant_id=tenant_id,
            sco_id=sco_id,
            transfers=[t.model_dump() for t in payload.transfers],
        )
        return {
            "sco_id": str(sco.sco_id),
            "status": sco.status,
            "transfers_processed": len(payload.transfers),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/receipts", status_code=status.HTTP_201_CREATED, summary="Create Subcontracting Receipt")
async def create_receipt(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: CreateReceiptSchema,
) -> Dict[str, Any]:
    try:
        scr = await subcontracting_service.receive_subcontracting_receipt(
            session=session,
            tenant_id=tenant_id,
            scr_number=payload.scr_number,
            sco_id=payload.sco_id,
            target_warehouse_id=payload.target_warehouse_id,
            finished_items_received=[it.model_dump() for it in payload.finished_items_received],
            posting_date=payload.posting_date,
        )
        return {
            "scr_id": str(scr.scr_id),
            "scr_number": scr.scr_number,
            "status": scr.status,
            "posting_date": scr.posting_date,
            "items_count": len(scr.items),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/receipts", summary="List Subcontracting Receipts")
async def list_receipts(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    sco_id: Optional[uuid.UUID] = Query(None),
) -> List[Dict[str, Any]]:
    receipts = await subcontracting_service.list_subcontracting_receipts(session, tenant_id, sco_id=sco_id)
    return [
        {
            "scr_id": str(r.scr_id),
            "scr_number": r.scr_number,
            "sco_id": str(r.sco_id),
            "supplier_id": str(r.supplier_id),
            "supplier_name": r.supplier.supplier_name if r.supplier else None,
            "target_warehouse_name": r.target_warehouse.warehouse_name if r.target_warehouse else None,
            "posting_date": r.posting_date,
            "status": r.status,
            "items": [
                {
                    "item_id": str(it.item_id),
                    "item_code": it.item.item_code if it.item else None,
                    "item_name": it.item.item_name if it.item else None,
                    "quantity_received": it.quantity_received,
                    "service_rate": it.service_rate,
                }
                for it in r.items
            ],
        }
        for r in receipts
    ]
