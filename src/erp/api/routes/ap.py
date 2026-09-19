"""Accounts Payable 3-Way Matching and Procurement API Endpoints."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
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


class CreateGRNRequest(BaseModel):
    grn_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    receipt_date: date


class CreateInvoiceRequest(BaseModel):
    invoice_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    grn_id: uuid.UUID | None = None
    invoice_date: date
    currency: str = "USD"
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.0000")


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
    """Records a warehouse delivery receipt note."""
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
    """Registers a vendor invoice for 3-way matching."""
    total_amount = req.subtotal + req.tax_amount
    inv = SupplierInvoice(
        tenant_id=tenant_id,
        invoice_number=req.invoice_number,
        supplier_id=req.supplier_id,
        po_id=req.po_id,
        grn_id=req.grn_id,
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
):
    """Executes automated 3-way match across invoice, PO, and GRN. Commits to GL if within tolerance."""
    try:
        return await three_way_matcher.match_invoice(
            session=db,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
