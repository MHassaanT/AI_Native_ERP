"""Accounts Payable 3-Way Matching and Procurement API Endpoints."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)
from erp.workflows.accounts_payable.three_way_matcher import (
    ThreeWayMatchResult,
    three_way_matcher,
)

router = APIRouter(prefix="/ap", tags=["Accounts Payable & 3-Way Match"])


class CreateSupplierRequest(BaseModel):
    supplier_code: str = Field(..., min_length=2, max_length=64)
    supplier_name: str = Field(..., min_length=2, max_length=255)
    tax_id: str | None = None
    currency: str = "USD"
    payment_terms_days: int = 30
    otif_score: Decimal = Decimal("100.00")


class CreatePOItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal


class CreatePurchaseOrderRequest(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    order_date: date
    currency: str = "USD"
    items: list[CreatePOItemRequest]


class CreateGRNItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity_received: Decimal
    unit_price: Decimal = Decimal("0.0000")
    po_item_id: uuid.UUID | None = None


class CreateGRNRequest(BaseModel):
    grn_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    receipt_date: date
    warehouse_id: uuid.UUID | None = None
    items: list[CreateGRNItemRequest] = Field(default_factory=list)


class CreateInvoiceItemRequest(BaseModel):
    item_code: str
    quantity: Decimal
    unit_price: Decimal
    item_id: uuid.UUID | None = None


class CreateInvoiceRequest(BaseModel):
    invoice_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    grn_id: uuid.UUID | None = None
    invoice_date: date
    currency: str = "USD"
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.0000")
    items: list[CreateInvoiceItemRequest] = Field(default_factory=list)



# --- Suppliers ---


@router.get("/suppliers", summary="List suppliers")
async def list_suppliers(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists suppliers for the tenant."""
    stmt = select(Supplier).where(Supplier.tenant_id == tenant_id).order_by(Supplier.supplier_code)
    return (await db.execute(stmt)).scalars().all()


@router.post("/suppliers", status_code=status.HTTP_201_CREATED, summary="Create supplier")
async def create_supplier(req: CreateSupplierRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Creates a new vendor supplier in PostgreSQL."""
    supplier = Supplier(
        tenant_id=tenant_id,
        supplier_code=req.supplier_code,
        supplier_name=req.supplier_name,
        tax_id=req.tax_id,
        currency=req.currency,
        payment_terms_days=req.payment_terms_days,
        otif_score=req.otif_score,
        is_active=True,
    )
    db.add(supplier)
    await db.flush()
    return supplier


# --- Purchase Orders ---


@router.get("/purchase-orders", summary="List purchase orders")
async def list_purchase_orders(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists purchase orders with lines for the tenant."""
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.tenant_id == tenant_id)
        .order_by(PurchaseOrder.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post(
    "/purchase-orders", status_code=status.HTTP_201_CREATED, summary="Create purchase order"
)
async def create_purchase_order(
    req: CreatePurchaseOrderRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Creates a purchase order and line items."""
    subtotal = sum(i.quantity * i.unit_price for i in req.items)
    po = PurchaseOrder(
        tenant_id=tenant_id,
        po_number=req.po_number,
        supplier_id=req.supplier_id,
        order_date=req.order_date,
        currency=req.currency,
        subtotal=subtotal,
        tax_amount=Decimal("0.0000"),
        total_amount=subtotal,
        status="SUBMITTED",
    )
    db.add(po)
    await db.flush()

    for itm in req.items:
        line = PurchaseOrderItem(
            tenant_id=tenant_id,
            po_id=po.po_id,
            item_id=itm.item_id,
            quantity=itm.quantity,
            unit_price=itm.unit_price,
            line_total=itm.quantity * itm.unit_price,
        )
        db.add(line)

    await db.flush()
    return po


# --- Goods Receipts ---


@router.get("/goods-receipts", summary="List goods receipt notes")
async def list_goods_receipts(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists goods receipt notes."""
    stmt = (
        select(GoodsReceiptNote)
        .where(GoodsReceiptNote.tenant_id == tenant_id)
        .order_by(GoodsReceiptNote.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/goods-receipts", status_code=status.HTTP_201_CREATED, summary="Create goods receipt")
async def create_goods_receipt(req: CreateGRNRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Records a warehouse delivery receipt note, increases on-hand inventory, and creates stock ledger entry."""
    from datetime import UTC, datetime

    grn = GoodsReceiptNote(
        tenant_id=tenant_id,
        grn_number=req.grn_number,
        supplier_id=req.supplier_id,
        po_id=req.po_id,
        receipt_date=req.receipt_date,
        status="COMPLETED",
    )
    db.add(grn)
    await db.flush()

    wh_id = req.warehouse_id
    if not wh_id:
        wh = (
            await db.execute(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.is_active.is_(True),
                )
            )
        ).scalars().first()
        if wh:
            wh_id = wh.warehouse_id

    items_to_process = list(req.items)
    if not items_to_process and req.po_id:
        po_items = (
            await db.execute(
                select(PurchaseOrderItem).where(
                    PurchaseOrderItem.tenant_id == tenant_id,
                    PurchaseOrderItem.po_id == req.po_id,
                )
            )
        ).scalars().all()
        for poi in po_items:
            items_to_process.append(
                CreateGRNItemRequest(
                    item_id=poi.item_id,
                    quantity_received=poi.quantity,
                    unit_price=poi.unit_price,
                    po_item_id=poi.item_line_id,
                )
            )

    for itm in items_to_process:
        grn_item = GoodsReceiptNoteItem(
            tenant_id=tenant_id,
            grn_id=grn.grn_id,
            po_item_id=itm.po_item_id,
            item_id=itm.item_id,
            quantity_received=itm.quantity_received,
            unit_price=itm.unit_price,
        )
        db.add(grn_item)

        if wh_id:
            stk = (
                await db.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == itm.item_id,
                        StockLevel.warehouse_id == wh_id,
                    )
                )
            ).scalar_one_or_none()

            if stk:
                stk.current_qty += itm.quantity_received
                stk.available_qty = stk.current_qty - stk.reserved_qty
                if itm.unit_price > 0:
                    stk.valuation_rate = itm.unit_price
                rate = stk.valuation_rate
                qty_after = stk.current_qty
            else:
                stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=itm.item_id,
                    warehouse_id=wh_id,
                    current_qty=itm.quantity_received,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=itm.quantity_received,
                    valuation_rate=itm.unit_price,
                )
                db.add(stk)
                rate = itm.unit_price
                qty_after = itm.quantity_received

            sle = StockLedgerEntry(
                tenant_id=tenant_id,
                posting_datetime=datetime.now(UTC),
                item_id=itm.item_id,
                warehouse_id=wh_id,
                actual_qty=itm.quantity_received,
                qty_after_transaction=qty_after,
                valuation_rate=rate,
                stock_value_difference=itm.quantity_received * rate,
                source_document_type="GOODS_RECEIPT",
                source_document_id=grn.grn_id,
            )
            db.add(sle)

    await db.flush()
    return grn


# --- Supplier Invoices & 3-Way Match ---


@router.get("/invoices", summary="List supplier invoices and match statuses")
async def list_supplier_invoices(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status_filter: str | None = Query(default=None),
):
    """Lists AP invoices filtered by tenant and optional matching status."""
    stmt = select(SupplierInvoice).where(SupplierInvoice.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(SupplierInvoice.matching_status == status_filter.upper())
    stmt = stmt.order_by(SupplierInvoice.created_at.desc())
    results = (await db.execute(stmt)).scalars().all()
    return results


@router.post("/invoices", status_code=status.HTTP_201_CREATED, summary="Create supplier invoice")
async def create_supplier_invoice(
    req: CreateInvoiceRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Registers a vendor invoice with line items for 3-way matching."""
    # Check for duplicate invoice number for the same tenant and supplier
    existing = (
        await db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.tenant_id == tenant_id,
                SupplierInvoice.supplier_id == req.supplier_id,
                SupplierInvoice.invoice_number == req.invoice_number,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invoice '{req.invoice_number}' already exists for this supplier (status: {existing.matching_status}). "
                "If goods were received after the invoice was recorded, please use 'Re-evaluate Match' on the existing invoice."
            ),
        )

    # If grn_id is not provided, check if a GRN already exists for po_id
    grn_id = req.grn_id
    if not grn_id and req.po_id:
        po_grn = (
            await db.execute(
                select(GoodsReceiptNote)
                .where(
                    GoodsReceiptNote.tenant_id == tenant_id,
                    GoodsReceiptNote.po_id == req.po_id,
                )
                .order_by(GoodsReceiptNote.created_at.desc())
            )
        ).scalars().first()
        if po_grn:
            grn_id = po_grn.grn_id

    total_amount = req.subtotal + req.tax_amount
    inv = SupplierInvoice(
        tenant_id=tenant_id,
        invoice_number=req.invoice_number,
        supplier_id=req.supplier_id,
        po_id=req.po_id,
        grn_id=grn_id,
        invoice_date=req.invoice_date,
        currency=req.currency,
        subtotal=req.subtotal,
        tax_amount=req.tax_amount,
        total_amount=total_amount,
        matching_status="UNMATCHED",
        variance_percentage=Decimal("0.0000"),
    )
    db.add(inv)
    await db.flush()

    from erp.db.models.inventory import Item

    if req.items:
        for itm in req.items:
            item_id = itm.item_id
            if not item_id:
                db_item = (
                    await db.execute(
                        select(Item).where(
                            Item.tenant_id == tenant_id,
                            Item.item_code == itm.item_code,
                        )
                    )
                ).scalar_one_or_none()
                if db_item:
                    item_id = db_item.item_id

            inv_item = SupplierInvoiceItem(
                tenant_id=tenant_id,
                invoice_id=inv.invoice_id,
                item_id=item_id,
                item_code=itm.item_code,
                quantity=itm.quantity,
                unit_price=itm.unit_price,
                line_total=itm.quantity * itm.unit_price,
            )
            db.add(inv_item)
    elif req.po_id:
        po_items = (
            await db.execute(
                select(PurchaseOrderItem, Item.item_code)
                .join(Item, PurchaseOrderItem.item_id == Item.item_id)
                .where(
                    PurchaseOrderItem.tenant_id == tenant_id,
                    PurchaseOrderItem.po_id == req.po_id,
                )
            )
        ).all()
        for po_item, code in po_items:
            inv_item = SupplierInvoiceItem(
                tenant_id=tenant_id,
                invoice_id=inv.invoice_id,
                item_id=po_item.item_id,
                item_code=code,
                quantity=po_item.quantity,
                unit_price=po_item.unit_price,
                line_total=po_item.quantity * po_item.unit_price,
            )
            db.add(inv_item)

    await db.flush()
    return inv



@router.post(
    "/match/{invoice_id}",
    response_model=ThreeWayMatchResult,
    summary="Trigger automated 3-way matching for invoice",
)
async def execute_invoice_matching(
    invoice_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    human_approved: bool = Query(default=False),
):
    """Executes automated 3-way match across invoice, PO, and GRN. Commits to GL if within tolerance."""
    try:
        return await three_way_matcher.match_invoice(
            session=db,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            human_approved=human_approved,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
