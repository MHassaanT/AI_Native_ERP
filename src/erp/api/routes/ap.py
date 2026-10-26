"""Accounts Payable 3-Way Matching and Procurement API Endpoints."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.shared_master import Address, Contact, ItemPrice, PriceList, TermsAndConditionsTemplate, UOM
from erp.db.models.phase_b import PurchaseTaxesAndChargesTemplate, ShippingRule
from erp.db.models.phase_b import SupplierGroup
from erp.db.models.onboarding import TenantSettings
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    DocumentAuditBatch,
    MaterialRequest,
    MaterialRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
    RFQItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierQuotation,
    SupplierQuotationItem,
)
from erp.workflows.accounts_payable.three_way_matcher import (
    ThreeWayMatchResult,
    three_way_matcher,
)
from erp.workflows.source_document_service import source_document_service
from erp.workflows.commercial.calculation_service import (
    CalculationLineInput,
    TaxRowInput,
    calculate_tax_rows,
    commercial_calculation_service,
    total_from_tax_snapshot,
)

router = APIRouter(prefix="/ap", tags=["Accounts Payable & 3-Way Match"])


class CreateSupplierRequest(BaseModel):
    supplier_code: str = Field(..., min_length=2, max_length=64)
    supplier_name: str = Field(..., min_length=2, max_length=255)
    tax_id: str | None = None
    currency: str = "USD"
    payment_terms_days: int = 30
    otif_score: Decimal = Decimal("100.00")
    supplier_group_id: uuid.UUID | None = None


class CreatePOItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    material_request_item_id: uuid.UUID | None = None
    rfq_item_id: uuid.UUID | None = None
    supplier_quotation_item_id: uuid.UUID | None = None
    uom_id: uuid.UUID | None = None
    conversion_factor: Decimal = Field(default=Decimal("1"), gt=0, max_digits=18, decimal_places=8)
    target_warehouse_id: uuid.UUID | None = None
    price_list_id: uuid.UUID | None = None
    item_price_id: uuid.UUID | None = None
    price_list_rate: Decimal | None = None


class CreatePurchaseOrderRequest(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    order_date: date
    currency: str = "USD"
    material_request_id: uuid.UUID | None = None
    supplier_contact_id: uuid.UUID | None = None
    supplier_address_id: uuid.UUID | None = None
    shipping_address_id: uuid.UUID | None = None
    terms_template_id: uuid.UUID | None = None
    terms_text: str | None = None
    payment_terms: str | None = None
    incoterm: str | None = Field(default=None, max_length=32)
    shipping_rule_id: uuid.UUID | None = None
    purchase_tax_template_id: uuid.UUID | None = None
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=0, max_digits=18, decimal_places=8)
    target_warehouse_id: uuid.UUID | None = None
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    taxes_and_charges: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    submit: bool = True
    items: list[CreatePOItemRequest] = Field(min_length=1, max_length=100)


class AmendPurchaseOrderRequest(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)


class CreateGRNItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity_received: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Decimal("0.0000")
    po_item_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None


class CreateGRNRequest(BaseModel):
    grn_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    receipt_date: date
    warehouse_id: uuid.UUID | None = None
    items: list[CreateGRNItemRequest] = Field(default_factory=list)


class CreateInvoiceItemRequest(BaseModel):
    item_code: str
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    item_id: uuid.UUID | None = None
    po_item_id: uuid.UUID | None = None
    grn_item_id: uuid.UUID | None = None


async def _calculate_purchase_tax_snapshot(
    db, *, tenant_id: uuid.UUID, template_id: uuid.UUID | None,
    net_total: Decimal, total_quantity: Decimal,
) -> tuple[Decimal, Decimal, list[dict] | None]:
    if template_id is None:
        return Decimal("0"), net_total, None
    template = await db.scalar(
        select(PurchaseTaxesAndChargesTemplate)
        .options(selectinload(PurchaseTaxesAndChargesTemplate.taxes))
        .where(
            PurchaseTaxesAndChargesTemplate.tenant_id == tenant_id,
            PurchaseTaxesAndChargesTemplate.template_id == template_id,
            PurchaseTaxesAndChargesTemplate.disabled.is_(False),
        )
    )
    if template is None:
        raise HTTPException(status_code=422, detail="Purchase tax template must be active and belong to this workspace.")
    tax_rows = []
    previous_row_id = None
    details = sorted(template.taxes, key=lambda row: (row.row_id or 0, str(row.detail_id)))
    for index, detail in enumerate(details, start=1):
        row_id = detail.row_id or index
        tax_rows.append(TaxRowInput(
            row_id=row_id,
            charge_type=detail.charge_type,
            rate=Decimal(detail.rate),
            description=detail.description,
            account_head=detail.account_head,
            reference_row=detail.reference_row or (previous_row_id if "Previous Row" in detail.charge_type else None),
            actual_amount=Decimal(detail.rate) if detail.charge_type == "Actual" else None,
            included_in_rate=detail.included_in_rate,
            add_deduct=detail.add_deduct,
            consider_for_valuation=detail.consider_for_valuation,
        ))
        previous_row_id = row_id
    try:
        result = calculate_tax_rows(net_total, total_quantity, tax_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    inputs_by_id = {row.row_id: row for row in tax_rows}
    snapshot = [{
        "row_id": row.row_id, "charge_type": row.charge_type,
        "description": row.description, "account_head": row.account_head,
        "rate": str(inputs_by_id[row.row_id].rate),
        "reference_row": inputs_by_id[row.row_id].reference_row,
        "actual_amount": str(inputs_by_id[row.row_id].actual_amount) if inputs_by_id[row.row_id].actual_amount is not None else None,
        "calculation_base": str(row.calculation_base), "amount": str(row.amount),
        "running_total": str(row.running_total), "included_in_rate": row.included_in_rate,
        "add_deduct": row.add_deduct, "consider_for_valuation": row.consider_for_valuation,
        "source_template_id": str(template.template_id),
    } for row in result.rows]
    return result.tax_total, result.grand_total, snapshot


def _tax_inputs_from_snapshot(snapshot: list[dict]) -> list[TaxRowInput]:
    inputs = []
    for row in snapshot:
        if "rate" not in row:
            raise HTTPException(
                status_code=409,
                detail="The linked purchase order has no reusable tax-rate snapshot; select a purchase tax template on this invoice.",
            )
        inputs.append(TaxRowInput(
            row_id=int(row["row_id"]),
            charge_type=row["charge_type"],
            rate=Decimal(str(row["rate"])),
            description=row["description"],
            account_head=row["account_head"],
            reference_row=int(row["reference_row"]) if row.get("reference_row") is not None else None,
            actual_amount=Decimal(str(row["actual_amount"])) if row.get("actual_amount") is not None else None,
            included_in_rate=bool(row.get("included_in_rate", False)),
            add_deduct=row.get("add_deduct", "ADD"),
            consider_for_valuation=bool(row.get("consider_for_valuation", False)),
        ))
    return inputs


class CreateInvoiceRequest(BaseModel):
    invoice_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    po_id: uuid.UUID | None = None
    grn_id: uuid.UUID | None = None
    invoice_date: date
    due_date: date | None = None
    currency: str = "USD"
    purchase_tax_template_id: uuid.UUID | None = None
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
    if req.supplier_group_id:
        group_id = await db.scalar(select(SupplierGroup.supplier_group_id).where(
            SupplierGroup.supplier_group_id == req.supplier_group_id,
            SupplierGroup.tenant_id == tenant_id,
            SupplierGroup.is_active.is_(True),
        ))
        if not group_id:
            raise HTTPException(status_code=422, detail="Supplier group must belong to this workspace and be active.")
    supplier = Supplier(
        tenant_id=tenant_id,
        supplier_group_id=req.supplier_group_id,
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
    supplier = await db.scalar(select(Supplier).where(
        Supplier.tenant_id == tenant_id,
        Supplier.supplier_id == req.supplier_id,
        Supplier.is_active.is_(True),
    ))
    if supplier is None:
        raise HTTPException(status_code=422, detail="Supplier must be active and belong to this workspace.")

    async def ensure_owned(model, pk, value, label: str):
        if value is None:
            return
        exists = await db.scalar(select(pk).where(model.tenant_id == tenant_id, pk == value))
        if exists is None:
            raise HTTPException(status_code=422, detail=f"{label} must belong to this workspace.")

    await ensure_owned(Contact, Contact.contact_id, req.supplier_contact_id, "Supplier contact")
    await ensure_owned(Address, Address.address_id, req.supplier_address_id, "Supplier address")
    await ensure_owned(Address, Address.address_id, req.shipping_address_id, "Shipping address")
    await ensure_owned(ShippingRule, ShippingRule.shipping_rule_id, req.shipping_rule_id, "Shipping rule")
    await ensure_owned(PurchaseTaxesAndChargesTemplate, PurchaseTaxesAndChargesTemplate.template_id, req.purchase_tax_template_id, "Purchase tax template")
    await ensure_owned(Warehouse, Warehouse.warehouse_id, req.target_warehouse_id, "Target warehouse")
    supplier_contact = None
    if req.supplier_contact_id:
        supplier_contact = await db.scalar(select(Contact).where(
            Contact.tenant_id == tenant_id, Contact.contact_id == req.supplier_contact_id,
            Contact.is_active.is_(True),
        ))
        if supplier_contact is None:
            raise HTTPException(status_code=422, detail="Supplier contact must be active and belong to this workspace.")
    address_ids = {value for value in (req.supplier_address_id, req.shipping_address_id) if value}
    address_rows = (await db.scalars(select(Address).where(
        Address.tenant_id == tenant_id, Address.address_id.in_(address_ids)
    ))).all() if address_ids else []
    addresses_by_id = {row.address_id: row for row in address_rows}
    if len(addresses_by_id) != len(address_ids):
        raise HTTPException(status_code=422, detail="Selected supplier and shipping addresses must belong to this workspace.")
    def address_snapshot(address):
        if address is None:
            return None
        return {key: getattr(address, key) for key in (
            "address_title", "address_type", "address_line1", "address_line2",
            "city", "state", "postal_code", "country",
        )}
    if req.terms_template_id:
        template = await db.scalar(select(TermsAndConditionsTemplate).where(
            TermsAndConditionsTemplate.tenant_id == tenant_id,
            TermsAndConditionsTemplate.terms_template_id == req.terms_template_id,
            TermsAndConditionsTemplate.is_active.is_(True),
            TermsAndConditionsTemplate.applicable_to.in_(("BUYING", "BOTH")),
        ))
        if template is None:
            raise HTTPException(status_code=422, detail="Terms template must be an active buying template in this workspace.")
    else:
        template = None
    terms_snapshot = req.terms_text if req.terms_text is not None else (template.terms if template else None)

    item_ids = {line.item_id for line in req.items}
    valid_items = set((await db.scalars(select(Item.item_id).where(
        Item.tenant_id == tenant_id, Item.item_id.in_(item_ids),
        Item.is_active.is_(True), Item.is_purchase_item.is_(True),
    ))).all())
    if valid_items != item_ids:
        raise HTTPException(status_code=422, detail="Every PO line must reference an active purchase item in this workspace.")
    mr_lines: dict[uuid.UUID, MaterialRequestItem] = {}
    if req.material_request_id:
        mr = await db.scalar(select(MaterialRequest).where(
            MaterialRequest.tenant_id == tenant_id,
            MaterialRequest.mr_id == req.material_request_id,
        ).with_for_update())
        if mr is None:
            raise HTTPException(status_code=422, detail="Material request must belong to this workspace.")
        if mr.status not in {"SUBMITTED", "PARTIALLY_ORDERED"}:
            raise HTTPException(status_code=409, detail="Only submitted or partially ordered material requests can source a purchase order.")
        mr_lines = {line.mr_item_id: line for line in (await db.scalars(select(MaterialRequestItem).where(
            MaterialRequestItem.tenant_id == tenant_id,
            MaterialRequestItem.mr_id == req.material_request_id,
        ).order_by(MaterialRequestItem.mr_item_id).with_for_update())).all()}
    mr_pending: dict[uuid.UUID, Decimal] = {}
    for line in req.items:
        await ensure_owned(UOM, UOM.uom_id, line.uom_id, "Unit of measure")
        await ensure_owned(Warehouse, Warehouse.warehouse_id, line.target_warehouse_id, "Line target warehouse")
        await ensure_owned(PriceList, PriceList.price_list_id, line.price_list_id, "Buying price list")
        if line.price_list_id:
            buying_list = await db.scalar(select(PriceList.price_list_id).where(
                PriceList.tenant_id == tenant_id, PriceList.price_list_id == line.price_list_id,
                PriceList.buying.is_(True), PriceList.is_active.is_(True),
            ))
            if buying_list is None:
                raise HTTPException(status_code=422, detail="Price list must be active and enabled for buying.")
        if line.item_price_id:
            item_price = await db.scalar(select(ItemPrice.item_price_id).where(
                ItemPrice.tenant_id == tenant_id, ItemPrice.item_price_id == line.item_price_id,
                ItemPrice.item_id == line.item_id,
                ItemPrice.price_list_id == line.price_list_id,
            ))
            if item_price is None:
                raise HTTPException(status_code=422, detail="Item price snapshot must match the item and price list on this line.")
        if line.material_request_item_id:
            mr_line = mr_lines.get(line.material_request_item_id)
            if mr_line is None or mr_line.item_id != line.item_id:
                raise HTTPException(status_code=422, detail="Material-request source line must match the selected parent request and item.")
            pending = mr_pending.get(mr_line.mr_item_id, Decimal("0"))
            if mr_line.ordered_qty + pending + line.quantity > mr_line.quantity:
                raise HTTPException(status_code=409, detail="Purchase quantity exceeds the material request line's remaining quantity.")
            draft_reserved = await db.scalar(select(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(
                PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id,
            ).where(
                PurchaseOrderItem.tenant_id == tenant_id,
                PurchaseOrderItem.material_request_item_id == mr_line.mr_item_id,
                PurchaseOrder.status == "DRAFT",
            ))
            if mr_line.ordered_qty + Decimal(str(draft_reserved or 0)) + pending + line.quantity > mr_line.quantity:
                raise HTTPException(status_code=409, detail="Purchase quantity exceeds the material request line's uncommitted remaining quantity.")
            mr_pending[mr_line.mr_item_id] = pending + line.quantity
        if line.rfq_item_id:
            rfq_line = await db.scalar(select(RFQItem).where(
                RFQItem.tenant_id == tenant_id, RFQItem.rfq_item_id == line.rfq_item_id,
                RFQItem.item_id == line.item_id,
            ))
            if rfq_line is None:
                raise HTTPException(status_code=422, detail="RFQ source line must match the selected item and workspace.")
        if line.supplier_quotation_item_id:
            quote_line = await db.scalar(select(SupplierQuotationItem).join(
                SupplierQuotation, SupplierQuotation.sq_id == SupplierQuotationItem.sq_id,
            ).where(
                SupplierQuotationItem.tenant_id == tenant_id,
                SupplierQuotationItem.sq_item_id == line.supplier_quotation_item_id,
                SupplierQuotationItem.item_id == line.item_id,
                SupplierQuotation.tenant_id == tenant_id,
                SupplierQuotation.supplier_id == req.supplier_id,
            ))
            if quote_line is None:
                raise HTTPException(status_code=422, detail="Supplier quotation line must match this supplier, item, and workspace.")

    if req.material_request_id and not mr_pending:
        raise HTTPException(status_code=422, detail="At least one purchase-order line must link to the selected material request.")

    calculation = await commercial_calculation_service.calculate(
        db, tenant_id=tenant_id, context="BUYING", currency=req.currency.upper(),
        use_tenant_default=True,
        shipping_rule_id=req.shipping_rule_id,
        destination_country=addresses_by_id.get(req.shipping_address_id).country if req.shipping_address_id else None,
        destination_state=addresses_by_id.get(req.shipping_address_id).state if req.shipping_address_id else None,
        lines=[CalculationLineInput(
            item_id=line.item_id, quantity=line.quantity, unit_price=line.unit_price,
            uom_id=line.uom_id, price_list_id=line.price_list_id,
        ) for line in req.items],
    )
    calculated_main_lines = [line for line in calculation.lines if not line.is_free]
    calculated_free_lines = [line for line in calculation.lines if line.is_free]
    gross_subtotal = sum((line.base_rate * line.entered_quantity for line in calculated_main_lines), Decimal("0"))
    line_discount = calculation.discount_total
    if req.discount_amount > gross_subtotal - line_discount:
        raise HTTPException(status_code=422, detail="Document discount cannot exceed the purchase-order subtotal.")
    taxable_base = gross_subtotal - line_discount - req.discount_amount + calculation.shipping_charge
    tax_amount, total, tax_snapshot = await _calculate_purchase_tax_snapshot(
        db, tenant_id=tenant_id, template_id=req.purchase_tax_template_id,
        net_total=taxable_base,
        total_quantity=sum((line.entered_quantity for line in calculation.lines), Decimal("0")),
    )
    if req.taxes_and_charges and req.taxes_and_charges != tax_amount:
        raise HTTPException(status_code=422, detail="Tax totals are calculated from the selected purchase tax template and cannot be supplied by the client.")
    if req.taxes_and_charges and req.purchase_tax_template_id is None:
        raise HTTPException(status_code=422, detail="Select a purchase tax template instead of supplying a tax total.")
    if total < 0:
        raise HTTPException(status_code=422, detail="Purchase order discount cannot exceed its subtotal and charges.")
    po = PurchaseOrder(
        tenant_id=tenant_id,
        po_number=req.po_number,
        supplier_id=req.supplier_id,
        order_date=req.order_date,
        currency=req.currency,
        subtotal=gross_subtotal,
        tax_amount=tax_amount,
        total_amount=total,
        status="SUBMITTED" if req.submit else "DRAFT",
        submitted_at=datetime.now(UTC) if req.submit else None,
        material_request_id=req.material_request_id,
        supplier_contact_id=req.supplier_contact_id,
        supplier_contact_snapshot=(
            {key: getattr(supplier_contact, key) for key in ("full_name", "email", "phone", "designation")}
            if supplier_contact else None
        ),
        supplier_address_id=req.supplier_address_id,
        supplier_address_snapshot=address_snapshot(addresses_by_id.get(req.supplier_address_id)),
        shipping_address_id=req.shipping_address_id,
        shipping_address_snapshot=address_snapshot(addresses_by_id.get(req.shipping_address_id)),
        terms_template_id=req.terms_template_id,
        purchase_tax_template_id=req.purchase_tax_template_id,
        tax_snapshot=tax_snapshot,
        terms_text=terms_snapshot,
        payment_terms=req.payment_terms or f"Net {supplier.payment_terms_days} days",
        incoterm=req.incoterm,
        shipping_rule_id=req.shipping_rule_id,
        exchange_rate=req.exchange_rate,
        target_warehouse_id=req.target_warehouse_id,
        discount_amount=req.discount_amount + line_discount,
        taxes_and_charges=tax_amount,
        shipping_charge=calculation.shipping_charge,
        calculation_hash=calculation.calculation_hash,
    )
    db.add(po)
    await db.flush()

    for itm, calculated in zip(req.items, calculated_main_lines, strict=True):
        line = PurchaseOrderItem(
            tenant_id=tenant_id,
            po_id=po.po_id,
            item_id=itm.item_id,
            quantity=itm.quantity,
            unit_price=calculated.base_rate,
            line_total=calculated.line_total,
            material_request_item_id=itm.material_request_item_id,
            rfq_item_id=itm.rfq_item_id,
            supplier_quotation_item_id=itm.supplier_quotation_item_id,
            uom_id=itm.uom_id,
            conversion_factor=calculated.conversion_factor,
            stock_quantity=calculated.stock_quantity,
            target_warehouse_id=itm.target_warehouse_id or req.target_warehouse_id,
            price_list_id=calculated.price_list_id,
            item_price_id=calculated.item_price_id or itm.item_price_id,
            price_list_rate=calculated.price_list_rate,
            discount_amount=calculated.discount_amount,
            pricing_rule_id=calculated.pricing_rule_id,
            promotion_id=calculated.promotion_id,
            is_free=calculated.is_free,
        )
        db.add(line)
    for calculated in calculated_free_lines:
        db.add(PurchaseOrderItem(
            tenant_id=tenant_id, po_id=po.po_id, item_id=calculated.item_id,
            quantity=calculated.entered_quantity, unit_price=Decimal("0"), line_total=Decimal("0"),
            conversion_factor=calculated.conversion_factor, stock_quantity=calculated.stock_quantity,
            price_list_id=calculated.price_list_id, price_list_rate=Decimal("0"),
            promotion_id=calculated.promotion_id, is_free=True,
        ))
    if req.submit:
        for mr_item_id, quantity in mr_pending.items():
            mr_lines[mr_item_id].ordered_qty += quantity
    if req.submit and req.material_request_id:
        mr = await db.scalar(select(MaterialRequest).where(
            MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == req.material_request_id,
        ).with_for_update())
        if mr:
            mr.status = "ORDERED" if all(item.ordered_qty >= item.quantity for item in mr_lines.values()) else "PARTIALLY_ORDERED"

    if req.submit:
        db.add(DocumentAuditBatch(
            tenant_id=tenant_id,
            operation="PURCHASE_ORDER_SUBMITTED",
            idempotency_key=str(po.po_id),
            status="COMPLETED",
            input_snapshot={"po_number": po.po_number, "supplier_id": str(po.supplier_id)},
            result_snapshot={"po_id": str(po.po_id), "status": po.status},
            completed_at=datetime.now(UTC),
        ))
    else:
        db.add(DocumentAuditBatch(
            tenant_id=tenant_id,
            operation="PURCHASE_ORDER_DRAFT_CREATED",
            idempotency_key=str(po.po_id),
            status="COMPLETED",
            input_snapshot={"po_number": po.po_number, "supplier_id": str(po.supplier_id)},
            result_snapshot={"po_id": str(po.po_id), "status": po.status},
            completed_at=datetime.now(UTC),
        ))

    await db.flush()
    return po


@router.post("/purchase-orders/{po_id}/recalculate", summary="Recalculate a purchase-order draft")
async def recalculate_purchase_order_draft(po_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    po = (await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ).with_for_update())).scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only a draft purchase order can be recalculated.")
    source_lines = [line for line in po.items if not line.is_free]
    previous_line_discount = sum((line.discount_amount for line in source_lines), Decimal("0"))
    document_discount = max(Decimal("0"), po.discount_amount - previous_line_discount)
    calculation = await commercial_calculation_service.calculate(
        db, tenant_id=tenant_id, context="BUYING", currency=po.currency,
        shipping_rule_id=po.shipping_rule_id,
        destination_country=(po.shipping_address_snapshot or {}).get("country"),
        destination_state=(po.shipping_address_snapshot or {}).get("state"),
        lines=[CalculationLineInput(item_id=line.item_id, quantity=line.quantity, unit_price=line.unit_price,
                                    uom_id=line.uom_id, price_list_id=line.price_list_id) for line in source_lines],
    )
    calculated_main_lines = [line for line in calculation.lines if not line.is_free]
    calculated_free_lines = [line for line in calculation.lines if line.is_free]
    if document_discount > sum((line.base_rate * line.entered_quantity for line in calculated_main_lines), Decimal("0")) - calculation.discount_total:
        raise HTTPException(status_code=422, detail="Document discount cannot exceed the purchase-order subtotal.")
    calculated_subtotal = sum((line.base_rate * line.entered_quantity for line in calculated_main_lines), Decimal("0"))
    calculated_discount = document_discount + calculation.discount_total
    tax_amount, calculated_total, tax_snapshot = await _calculate_purchase_tax_snapshot(
        db, tenant_id=tenant_id, template_id=po.purchase_tax_template_id,
        net_total=calculated_subtotal - calculated_discount + calculation.shipping_charge,
        total_quantity=sum((line.entered_quantity for line in calculation.lines), Decimal("0")),
    )
    for stored, calculated in zip(source_lines, calculated_main_lines, strict=True):
        stored.unit_price = calculated.base_rate
        stored.line_total = calculated.line_total
        stored.conversion_factor = calculated.conversion_factor
        stored.stock_quantity = calculated.stock_quantity
        stored.price_list_id = calculated.price_list_id
        stored.item_price_id = calculated.item_price_id
        stored.price_list_rate = calculated.price_list_rate
        stored.discount_amount = calculated.discount_amount
        stored.pricing_rule_id = calculated.pricing_rule_id
        stored.promotion_id = calculated.promotion_id
    for line in po.items:
        if line.is_free:
            await db.delete(line)
    for calculated in calculated_free_lines:
        db.add(PurchaseOrderItem(
            tenant_id=tenant_id, po_id=po.po_id, item_id=calculated.item_id,
            quantity=calculated.entered_quantity, unit_price=Decimal("0"), line_total=Decimal("0"),
            conversion_factor=calculated.conversion_factor, stock_quantity=calculated.stock_quantity,
            price_list_id=calculated.price_list_id, price_list_rate=Decimal("0"),
            promotion_id=calculated.promotion_id, is_free=True,
        ))
    po.subtotal = calculated_subtotal
    po.discount_amount = calculated_discount
    po.tax_amount = tax_amount
    po.taxes_and_charges = tax_amount
    po.tax_snapshot = tax_snapshot
    po.shipping_charge = calculation.shipping_charge
    po.calculation_hash = calculation.calculation_hash
    po.total_amount = calculated_total
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="PURCHASE_ORDER_DRAFT_RECALCULATED",
        idempotency_key=f"{po.po_id}:{datetime.now(UTC).isoformat()}", status="COMPLETED",
        input_snapshot={"po_id": str(po.po_id)},
        result_snapshot={"calculation_hash": calculation.calculation_hash, "total": str(po.total_amount)},
        completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return {"po_id": str(po.po_id), "subtotal": po.subtotal, "total_amount": po.total_amount, "status": po.status}


@router.put("/purchase-orders/{po_id}/draft", summary="Replace a purchase-order draft")
async def update_purchase_order_draft(
    po_id: uuid.UUID, req: CreatePurchaseOrderRequest, tenant_id: TenantIdDep, db: DbSessionDep,
):
    """Replace editable draft details/lines without changing committed source progress."""
    po = (await db.execute(select(PurchaseOrder).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ).with_for_update())).scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only a draft purchase order can be edited.")
    supplier = await db.scalar(select(Supplier).where(
        Supplier.tenant_id == tenant_id, Supplier.supplier_id == req.supplier_id, Supplier.is_active.is_(True),
    ))
    if supplier is None:
        raise HTTPException(status_code=422, detail="Supplier must be active and belong to this workspace.")
    duplicate = await db.scalar(select(PurchaseOrder.po_id).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_number == req.po_number, PurchaseOrder.po_id != po_id,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="Purchase-order number already exists in this workspace.")
    item_ids = {line.item_id for line in req.items}
    valid_items = set((await db.scalars(select(Item.item_id).where(
        Item.tenant_id == tenant_id, Item.item_id.in_(item_ids), Item.is_active.is_(True), Item.is_purchase_item.is_(True),
    ))).all())
    if valid_items != item_ids:
        raise HTTPException(status_code=422, detail="Every PO line must reference an active purchase item in this workspace.")
    async def owned(model, column, value, label):
        if value is not None and await db.scalar(select(column).where(model.tenant_id == tenant_id, column == value)) is None:
            raise HTTPException(status_code=422, detail=f"{label} must belong to this workspace.")
    for model, column, value, label in (
        (Contact, Contact.contact_id, req.supplier_contact_id, "Supplier contact"),
        (Address, Address.address_id, req.supplier_address_id, "Supplier address"),
        (Address, Address.address_id, req.shipping_address_id, "Shipping address"),
        (ShippingRule, ShippingRule.shipping_rule_id, req.shipping_rule_id, "Shipping rule"),
        (PurchaseTaxesAndChargesTemplate, PurchaseTaxesAndChargesTemplate.template_id, req.purchase_tax_template_id, "Purchase tax template"),
        (Warehouse, Warehouse.warehouse_id, req.target_warehouse_id, "Target warehouse"),
    ):
        await owned(model, column, value, label)
    contact = await db.scalar(select(Contact).where(
        Contact.tenant_id == tenant_id, Contact.contact_id == req.supplier_contact_id, Contact.is_active.is_(True),
    )) if req.supplier_contact_id else None
    if req.supplier_contact_id and contact is None:
        raise HTTPException(status_code=422, detail="Supplier contact must be active.")
    addresses = (await db.scalars(select(Address).where(
        Address.tenant_id == tenant_id,
        Address.address_id.in_({value for value in (req.supplier_address_id, req.shipping_address_id) if value}),
    ))).all() if req.supplier_address_id or req.shipping_address_id else []
    address_by_id = {row.address_id: row for row in addresses}
    if req.terms_template_id:
        template = await db.scalar(select(TermsAndConditionsTemplate).where(
            TermsAndConditionsTemplate.tenant_id == tenant_id,
            TermsAndConditionsTemplate.terms_template_id == req.terms_template_id,
            TermsAndConditionsTemplate.is_active.is_(True),
            TermsAndConditionsTemplate.applicable_to.in_(("BUYING", "BOTH")),
        ))
        if template is None:
            raise HTTPException(status_code=422, detail="Terms template must be an active buying template in this workspace.")
    else:
        template = None
    mr_lines: dict[uuid.UUID, MaterialRequestItem] = {}
    if req.material_request_id:
        mr = await db.scalar(select(MaterialRequest).where(
            MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == req.material_request_id,
        ).with_for_update())
        if mr is None or mr.status not in {"SUBMITTED", "PARTIALLY_ORDERED"}:
            raise HTTPException(status_code=409, detail="Material request must be open and belong to this workspace.")
        mr_lines = {row.mr_item_id: row for row in (await db.scalars(select(MaterialRequestItem).where(
            MaterialRequestItem.tenant_id == tenant_id, MaterialRequestItem.mr_id == req.material_request_id,
        ).order_by(MaterialRequestItem.mr_item_id).with_for_update())).all()}
    wanted: dict[uuid.UUID, Decimal] = {}
    for line in req.items:
        for model, column, value, label in (
            (UOM, UOM.uom_id, line.uom_id, "Unit of measure"),
            (Warehouse, Warehouse.warehouse_id, line.target_warehouse_id, "Line target warehouse"),
            (PriceList, PriceList.price_list_id, line.price_list_id, "Price list"),
        ):
            await owned(model, column, value, label)
        if line.material_request_item_id:
            source = mr_lines.get(line.material_request_item_id)
            if source is None or source.item_id != line.item_id:
                raise HTTPException(status_code=422, detail="Material-request source line must match the selected parent request and item.")
            wanted[source.mr_item_id] = wanted.get(source.mr_item_id, Decimal("0")) + line.quantity
        if line.rfq_item_id and await db.scalar(select(RFQItem.rfq_item_id).where(
            RFQItem.tenant_id == tenant_id, RFQItem.rfq_item_id == line.rfq_item_id, RFQItem.item_id == line.item_id,
        )) is None:
            raise HTTPException(status_code=422, detail="RFQ source line must match this item and workspace.")
        if line.supplier_quotation_item_id and await db.scalar(select(SupplierQuotationItem.sq_item_id).join(
            SupplierQuotation, SupplierQuotation.sq_id == SupplierQuotationItem.sq_id,
        ).where(
            SupplierQuotationItem.tenant_id == tenant_id, SupplierQuotationItem.sq_item_id == line.supplier_quotation_item_id,
            SupplierQuotationItem.item_id == line.item_id, SupplierQuotation.tenant_id == tenant_id,
            SupplierQuotation.supplier_id == req.supplier_id,
        )) is None:
            raise HTTPException(status_code=422, detail="Supplier quotation source must match this supplier, item, and workspace.")
    if req.material_request_id and not wanted:
        raise HTTPException(status_code=422, detail="At least one PO line must link to the selected material request.")
    for source_id, quantity in wanted.items():
        source = mr_lines[source_id]
        other_drafts = await db.scalar(select(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0)).join(
            PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id,
        ).where(
            PurchaseOrderItem.tenant_id == tenant_id, PurchaseOrderItem.material_request_item_id == source_id,
            PurchaseOrder.status == "DRAFT", PurchaseOrder.po_id != po_id,
        ))
        if source.ordered_qty + Decimal(str(other_drafts or 0)) + quantity > source.quantity:
            raise HTTPException(status_code=409, detail="Purchase quantity exceeds the material request line's remaining quantity.")
    calculation = await commercial_calculation_service.calculate(
        db, tenant_id=tenant_id, context="BUYING", currency=req.currency.upper(),
        shipping_rule_id=req.shipping_rule_id,
        destination_country=address_by_id.get(req.shipping_address_id).country if req.shipping_address_id else None,
        destination_state=address_by_id.get(req.shipping_address_id).state if req.shipping_address_id else None,
        lines=[CalculationLineInput(item_id=line.item_id, quantity=line.quantity, unit_price=line.unit_price,
                                    uom_id=line.uom_id, price_list_id=line.price_list_id) for line in req.items],
    )
    calculated_main_lines = [line for line in calculation.lines if not line.is_free]
    calculated_free_lines = [line for line in calculation.lines if line.is_free]
    subtotal = sum((line.base_rate * line.entered_quantity for line in calculated_main_lines), Decimal("0"))
    line_discount = calculation.discount_total
    if req.discount_amount > subtotal - line_discount:
        raise HTTPException(status_code=422, detail="Document discount cannot exceed the purchase-order subtotal.")
    tax_amount, calculated_total, tax_snapshot = await _calculate_purchase_tax_snapshot(
        db, tenant_id=tenant_id, template_id=req.purchase_tax_template_id,
        net_total=subtotal - line_discount - req.discount_amount + calculation.shipping_charge,
        total_quantity=sum((line.entered_quantity for line in calculation.lines), Decimal("0")),
    )
    if req.taxes_and_charges and req.taxes_and_charges != tax_amount:
        raise HTTPException(status_code=422, detail="Tax totals are calculated from the selected purchase tax template and cannot be supplied by the client.")
    for old_line in (await db.scalars(select(PurchaseOrderItem).where(
        PurchaseOrderItem.tenant_id == tenant_id, PurchaseOrderItem.po_id == po_id,
    ).with_for_update())).all():
        await db.delete(old_line)
    po.po_number = req.po_number
    po.supplier_id = req.supplier_id
    po.order_date = req.order_date
    po.currency = req.currency
    po.material_request_id = req.material_request_id
    po.supplier_contact_id = req.supplier_contact_id
    po.supplier_contact_snapshot = ({key: getattr(contact, key) for key in ("full_name", "email", "phone", "designation")} if contact else None)
    po.supplier_address_id = req.supplier_address_id
    po.supplier_address_snapshot = ({key: getattr(address_by_id[req.supplier_address_id], key) for key in ("address_title", "address_type", "address_line1", "address_line2", "city", "state", "postal_code", "country")} if req.supplier_address_id else None)
    po.shipping_address_id = req.shipping_address_id
    po.shipping_address_snapshot = ({key: getattr(address_by_id[req.shipping_address_id], key) for key in ("address_title", "address_type", "address_line1", "address_line2", "city", "state", "postal_code", "country")} if req.shipping_address_id else None)
    po.terms_template_id = req.terms_template_id
    po.terms_text = req.terms_text if req.terms_text is not None else (template.terms if template else None)
    po.payment_terms = req.payment_terms or f"Net {supplier.payment_terms_days} days"
    po.incoterm = req.incoterm
    po.shipping_rule_id = req.shipping_rule_id
    po.purchase_tax_template_id = req.purchase_tax_template_id
    po.exchange_rate = req.exchange_rate
    po.target_warehouse_id = req.target_warehouse_id
    po.discount_amount = req.discount_amount + line_discount
    po.taxes_and_charges = tax_amount
    po.tax_amount = tax_amount
    po.tax_snapshot = tax_snapshot
    po.subtotal = subtotal
    po.shipping_charge = calculation.shipping_charge
    po.calculation_hash = calculation.calculation_hash
    po.total_amount = calculated_total
    for line, calculated in zip(req.items, calculated_main_lines, strict=True):
        db.add(PurchaseOrderItem(
            tenant_id=tenant_id, po_id=po.po_id, item_id=line.item_id, quantity=line.quantity,
            unit_price=calculated.base_rate, line_total=calculated.line_total,
            material_request_item_id=line.material_request_item_id, rfq_item_id=line.rfq_item_id,
            supplier_quotation_item_id=line.supplier_quotation_item_id, uom_id=line.uom_id,
            conversion_factor=calculated.conversion_factor, stock_quantity=calculated.stock_quantity,
            target_warehouse_id=line.target_warehouse_id or req.target_warehouse_id,
            price_list_id=calculated.price_list_id, item_price_id=calculated.item_price_id or line.item_price_id,
            price_list_rate=calculated.price_list_rate, discount_amount=calculated.discount_amount,
            pricing_rule_id=calculated.pricing_rule_id, promotion_id=calculated.promotion_id, is_free=calculated.is_free,
        ))
    for calculated in calculated_free_lines:
        db.add(PurchaseOrderItem(
            tenant_id=tenant_id, po_id=po.po_id, item_id=calculated.item_id,
            quantity=calculated.entered_quantity, unit_price=Decimal("0"), line_total=Decimal("0"),
            conversion_factor=calculated.conversion_factor, stock_quantity=calculated.stock_quantity,
            price_list_id=calculated.price_list_id, price_list_rate=Decimal("0"),
            promotion_id=calculated.promotion_id, is_free=True,
        ))
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="PURCHASE_ORDER_DRAFT_UPDATED", idempotency_key=f"{po.po_id}:{datetime.now(UTC).isoformat()}",
        status="COMPLETED", input_snapshot={"po_number": req.po_number},
        result_snapshot={"po_id": str(po.po_id), "status": po.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return po


@router.post("/purchase-orders/{po_id}/submit", summary="Submit a purchase-order draft")
async def submit_purchase_order(po_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    po = (await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ).with_for_update())).scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status == "SUBMITTED":
        return po
    if po.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only a draft purchase order can be submitted.")
    if po.amended_from_po_id:
        original = await db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po.amended_from_po_id,
        ).with_for_update())
        if original is None or original.status != "CANCELLED":
            raise HTTPException(status_code=409, detail="Cancel the original purchase order before submitting its amendment.")
    supplier = await db.scalar(select(Supplier.supplier_id).where(
        Supplier.tenant_id == tenant_id, Supplier.supplier_id == po.supplier_id, Supplier.is_active.is_(True),
    ))
    if supplier is None or not po.items:
        raise HTTPException(status_code=409, detail="An active supplier and at least one purchase-order line are required.")
    expected_total = total_from_tax_snapshot(
        po.subtotal - po.discount_amount + po.shipping_charge, po.tax_snapshot,
    )
    if po.discount_amount > po.subtotal or po.total_amount != expected_total or not po.calculation_hash:
        raise HTTPException(status_code=409, detail="Recalculate the purchase-order draft before submitting.")
    mr_line_totals: dict[uuid.UUID, Decimal] = {}
    for line in po.items:
        item_exists = await db.scalar(select(Item.item_id).where(
            Item.tenant_id == tenant_id, Item.item_id == line.item_id, Item.is_active.is_(True), Item.is_purchase_item.is_(True),
        ))
        if item_exists is None:
            raise HTTPException(status_code=409, detail="Every purchase-order item must remain active in this workspace.")
        if line.material_request_item_id:
            mr_line_totals[line.material_request_item_id] = mr_line_totals.get(line.material_request_item_id, Decimal("0")) + line.quantity
    if mr_line_totals:
        mr_lines = {row.mr_item_id: row for row in (await db.scalars(select(MaterialRequestItem).where(
            MaterialRequestItem.tenant_id == tenant_id,
            MaterialRequestItem.mr_item_id.in_(mr_line_totals),
        ).order_by(MaterialRequestItem.mr_item_id).with_for_update())).all()}
        if set(mr_lines) != set(mr_line_totals):
            raise HTTPException(status_code=409, detail="A linked material-request line is no longer available.")
        for source_id, quantity in mr_line_totals.items():
            source = mr_lines[source_id]
            if source.ordered_qty + quantity > source.quantity:
                raise HTTPException(status_code=409, detail="Purchase order exceeds the linked material request's remaining quantity.")
        for source_id, quantity in mr_line_totals.items():
            mr_lines[source_id].ordered_qty += quantity
        request_ids = {row.mr_id for row in mr_lines.values()}
        for request_id in request_ids:
            request = await db.scalar(select(MaterialRequest).where(
                MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == request_id,
            ).with_for_update())
            if request is None or request.status not in {"SUBMITTED", "PARTIALLY_ORDERED"}:
                raise HTTPException(status_code=409, detail="Linked material request must be submitted and still open.")
            await source_document_service.refresh_material_request_progress(db, tenant_id, request_id)
    po.status = "SUBMITTED"
    po.submitted_at = datetime.now(UTC)
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="PURCHASE_ORDER_SUBMITTED", idempotency_key=str(po.po_id),
        status="COMPLETED", input_snapshot={"po_id": str(po.po_id)},
        result_snapshot={"po_number": po.po_number, "status": po.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return po


@router.post("/purchase-orders/{po_id}/cancel", summary="Cancel a purchase order")
async def cancel_purchase_order(po_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    po = (await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ).with_for_update())).scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status == "CANCELLED":
        return po
    if po.status not in {"DRAFT", "SUBMITTED"}:
        raise HTTPException(status_code=409, detail="Only a draft or submitted purchase order can be cancelled.")
    linked_receipt = await db.scalar(select(GoodsReceiptNote.grn_id).where(
        GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNote.po_id == po.po_id,
    ).limit(1).with_for_update())
    if linked_receipt:
        raise HTTPException(status_code=409, detail="A purchase order with goods receipts cannot be cancelled; process a return or credit note.")
    linked_invoice = await db.scalar(select(SupplierInvoice.invoice_id).where(
        SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == po.po_id,
    ).limit(1).with_for_update())
    if linked_invoice:
        raise HTTPException(status_code=409, detail="A purchase order with supplier invoices cannot be cancelled.")
    if po.status == "SUBMITTED":
        grouped: dict[uuid.UUID, Decimal] = {}
        for line in po.items:
            if line.material_request_item_id:
                grouped[line.material_request_item_id] = grouped.get(line.material_request_item_id, Decimal("0")) + line.quantity
        if grouped:
            source_lines = {row.mr_item_id: row for row in (await db.scalars(select(MaterialRequestItem).where(
                MaterialRequestItem.tenant_id == tenant_id, MaterialRequestItem.mr_item_id.in_(grouped),
            ).order_by(MaterialRequestItem.mr_item_id).with_for_update())).all()}
            if set(source_lines) != set(grouped):
                raise HTTPException(status_code=409, detail="A linked material-request line is no longer available to release.")
            for source_id, quantity in grouped.items():
                if source_id in source_lines:
                    source_lines[source_id].ordered_qty = max(Decimal("0"), source_lines[source_id].ordered_qty - quantity)
            for request_id in {row.mr_id for row in source_lines.values()}:
                request = await db.scalar(select(MaterialRequest).where(
                    MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == request_id,
                ).with_for_update())
                if request:
                    await source_document_service.refresh_material_request_progress(db, tenant_id, request_id)
    po.status = "CANCELLED"
    po.cancelled_at = datetime.now(UTC)
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="PURCHASE_ORDER_CANCELLED", idempotency_key=str(po.po_id),
        status="COMPLETED", input_snapshot={"po_id": str(po.po_id)},
        result_snapshot={"po_number": po.po_number, "status": po.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return po


@router.post("/purchase-orders/{po_id}/amend", status_code=status.HTTP_201_CREATED, summary="Create a new draft amendment")
async def amend_purchase_order(po_id: uuid.UUID, req: AmendPurchaseOrderRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    original = (await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ).with_for_update())).scalar_one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if original.status != "SUBMITTED":
        raise HTTPException(status_code=409, detail="Only a submitted purchase order can be amended.")
    duplicate = await db.scalar(select(PurchaseOrder.po_id).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_number == req.po_number,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="Purchase-order number already exists in this workspace.")
    has_downstream = await db.scalar(select(GoodsReceiptNote.grn_id).where(
        GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNote.po_id == original.po_id,
    ).limit(1))
    if has_downstream:
        raise HTTPException(status_code=409, detail="An order with goods receipts must be resolved through returns or credit notes before amendment.")
    has_invoice = await db.scalar(select(SupplierInvoice.invoice_id).where(
        SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == original.po_id,
    ).limit(1))
    if has_invoice:
        raise HTTPException(status_code=409, detail="An order with supplier invoices cannot be amended.")
    revision = PurchaseOrder(
        tenant_id=tenant_id, po_number=req.po_number, supplier_id=original.supplier_id,
        order_date=date.today(), currency=original.currency, subtotal=original.subtotal,
        tax_amount=original.tax_amount, total_amount=original.total_amount, status="DRAFT",
        amended_from_po_id=original.po_id, material_request_id=original.material_request_id,
        supplier_contact_id=original.supplier_contact_id, supplier_contact_snapshot=original.supplier_contact_snapshot,
        supplier_address_id=original.supplier_address_id, supplier_address_snapshot=original.supplier_address_snapshot,
        shipping_address_id=original.shipping_address_id, shipping_address_snapshot=original.shipping_address_snapshot,
        terms_template_id=original.terms_template_id, terms_text=original.terms_text,
        payment_terms=original.payment_terms, incoterm=original.incoterm, shipping_rule_id=original.shipping_rule_id,
        exchange_rate=original.exchange_rate, target_warehouse_id=original.target_warehouse_id,
        discount_amount=original.discount_amount, taxes_and_charges=original.taxes_and_charges,
    )
    db.add(revision)
    await db.flush()
    for item in original.items:
        db.add(PurchaseOrderItem(
            tenant_id=tenant_id, po_id=revision.po_id, item_id=item.item_id, quantity=item.quantity,
            unit_price=item.unit_price, line_total=item.line_total,
            material_request_item_id=item.material_request_item_id, rfq_item_id=item.rfq_item_id,
            supplier_quotation_item_id=item.supplier_quotation_item_id, uom_id=item.uom_id,
            conversion_factor=item.conversion_factor, stock_quantity=item.stock_quantity,
            target_warehouse_id=item.target_warehouse_id, price_list_id=item.price_list_id,
            item_price_id=item.item_price_id, price_list_rate=item.price_list_rate,
        ))
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="PURCHASE_ORDER_AMENDMENT_CREATED", idempotency_key=str(revision.po_id),
        status="COMPLETED", input_snapshot={"original_po_id": str(original.po_id)},
        result_snapshot={"po_id": str(revision.po_id), "status": revision.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return revision


@router.get("/purchase-orders/{po_id}/timeline", summary="Purchase order source links and audit timeline")
async def purchase_order_timeline(po_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    po = (await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_id == po_id,
    ))).scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    receipts = (await db.scalars(select(GoodsReceiptNote).options(selectinload(GoodsReceiptNote.items)).where(
        GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNote.po_id == po_id,
    ).order_by(GoodsReceiptNote.receipt_date))).all()
    invoices = (await db.scalars(select(SupplierInvoice).options(selectinload(SupplierInvoice.items)).where(
        SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == po_id,
    ).order_by(SupplierInvoice.invoice_date))).all()
    events = (await db.scalars(select(DocumentAuditBatch).where(
        DocumentAuditBatch.tenant_id == tenant_id,
        DocumentAuditBatch.idempotency_key == str(po_id),
        DocumentAuditBatch.operation.like("PURCHASE_ORDER_%"),
    ).order_by(DocumentAuditBatch.created_at))).all()
    return {"document": po, "source_links": {"material_request_id": str(po.material_request_id) if po.material_request_id else None,
        "amended_from_po_id": str(po.amended_from_po_id) if po.amended_from_po_id else None,
        "lines": [{"po_item_id": str(line.item_line_id), "quantity": line.quantity,
            "received_quantity": sum((receipt_line.quantity_received for receipt in receipts for receipt_line in receipt.items if receipt_line.po_item_id == line.item_line_id), Decimal("0")),
            "billed_quantity": sum((invoice_line.quantity for invoice in invoices for invoice_line in invoice.items if invoice_line.po_item_id == line.item_line_id), Decimal("0")),
            "remaining_to_receive": max(Decimal("0"), line.quantity - sum((receipt_line.quantity_received for receipt in receipts for receipt_line in receipt.items if receipt_line.po_item_id == line.item_line_id), Decimal("0"))),
            "remaining_to_bill": max(Decimal("0"), line.quantity - sum((invoice_line.quantity for invoice in invoices for invoice_line in invoice.items if invoice_line.po_item_id == line.item_line_id), Decimal("0"))),
            "material_request_item_id": str(line.material_request_item_id) if line.material_request_item_id else None,
            "rfq_item_id": str(line.rfq_item_id) if line.rfq_item_id else None,
            "supplier_quotation_item_id": str(line.supplier_quotation_item_id) if line.supplier_quotation_item_id else None} for line in po.items]},
        "goods_receipts": receipts, "supplier_invoices": invoices, "audit_events": events}


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
                    warehouse_id=poi.target_warehouse_id,
                )
            )

    po_lines_by_id: dict[uuid.UUID, PurchaseOrderItem] = {}
    po_for_receipt: PurchaseOrder | None = None
    received_total_by_line: dict[uuid.UUID, Decimal] = {}
    if req.po_id:
        po = await db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_id == req.po_id, PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.supplier_id == req.supplier_id).with_for_update())
        if po is None:
            raise HTTPException(status_code=404, detail="Purchase order not found for this supplier and workspace.")
        if po.status not in {"SUBMITTED", "PARTIALLY_RECEIVED"}:
            raise HTTPException(status_code=409, detail="Goods can only be received against a submitted, open purchase order.")
        po_for_receipt = po
        settings = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
        tolerance = settings.over_receipt_percentage if settings else Decimal("0")
        po_lines = (await db.scalars(select(PurchaseOrderItem).where(PurchaseOrderItem.tenant_id == tenant_id, PurchaseOrderItem.po_id == req.po_id).order_by(PurchaseOrderItem.item_line_id).with_for_update())).all()
        po_lines_by_id = {line.item_line_id: line for line in po_lines}
        pending_by_po_item: dict[uuid.UUID, Decimal] = {}
        for receipt_line in items_to_process:
            matches = [line for line in po_lines if line.item_line_id == receipt_line.po_item_id] if receipt_line.po_item_id else [line for line in po_lines if line.item_id == receipt_line.item_id]
            if len(matches) != 1:
                if len(matches) > 1:
                    raise HTTPException(status_code=422, detail="Receipt item matches multiple purchase-order lines; provide po_item_id to disambiguate.")
                raise HTTPException(status_code=422, detail="Every purchase receipt line must match a line on its purchase order.")
            po_line = matches[0]
            receipt_line.po_item_id = po_line.item_line_id
            received_before = await db.scalar(select(func.coalesce(func.sum(GoodsReceiptNoteItem.quantity_received), 0)).join(GoodsReceiptNote, GoodsReceiptNote.grn_id == GoodsReceiptNoteItem.grn_id).where(GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNote.po_id == req.po_id, GoodsReceiptNoteItem.tenant_id == tenant_id, GoodsReceiptNoteItem.po_item_id == po_line.item_line_id))
            received_total_by_line[po_line.item_line_id] = Decimal(str(received_before or 0))
            allowed = po_line.quantity * (Decimal("1") + tolerance / Decimal("100"))
            pending = pending_by_po_item.get(po_line.item_line_id, Decimal("0"))
            if Decimal(str(received_before or 0)) + pending + receipt_line.quantity_received > allowed:
                raise HTTPException(status_code=409, detail=f"Receipt quantity for item {po_line.item_id} exceeds the {tolerance}% over-receipt tolerance.")
            pending_by_po_item[po_line.item_line_id] = pending + receipt_line.quantity_received
        if po_lines:
            fully_received = all(
                received_total_by_line.get(line.item_line_id, Decimal("0"))
                + pending_by_po_item.get(line.item_line_id, Decimal("0")) >= line.quantity
                for line in po_lines
            )
            po.status = "COMPLETED" if fully_received else "PARTIALLY_RECEIVED"

    for itm in items_to_process:
        po_line = po_lines_by_id.get(itm.po_item_id) if itm.po_item_id else None
        conversion_factor = po_line.conversion_factor if po_line else Decimal("1")
        stock_quantity = itm.quantity_received * conversion_factor
        line_warehouse_id = itm.warehouse_id or (po_line.target_warehouse_id if po_line else None) or wh_id
        if line_warehouse_id is None:
            raise HTTPException(status_code=422, detail="Each receipt line needs an active receiving warehouse.")
        receiving_warehouse = await db.scalar(select(Warehouse).where(
            Warehouse.tenant_id == tenant_id,
            Warehouse.warehouse_id == line_warehouse_id,
            Warehouse.is_active.is_(True),
        ))
        if receiving_warehouse is None:
            raise HTTPException(status_code=422, detail="Receipt warehouse must be active and belong to this workspace.")
        grn_item = GoodsReceiptNoteItem(
            tenant_id=tenant_id,
            grn_id=grn.grn_id,
            po_item_id=itm.po_item_id,
            item_id=itm.item_id,
            quantity_received=itm.quantity_received,
            quantity_accepted=itm.quantity_received,
            conversion_factor=conversion_factor,
            stock_quantity=stock_quantity,
            warehouse_id=line_warehouse_id,
            unit_price=itm.unit_price,
            material_request_item_id=(po_lines_by_id[itm.po_item_id].material_request_item_id if itm.po_item_id in po_lines_by_id else None),
            supplier_quotation_item_id=(po_lines_by_id[itm.po_item_id].supplier_quotation_item_id if itm.po_item_id in po_lines_by_id else None),
        )
        db.add(grn_item)

        if line_warehouse_id:
            stk = (
                await db.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == itm.item_id,
                        StockLevel.warehouse_id == line_warehouse_id,
                    )
                )
            ).scalar_one_or_none()

            if stk:
                stk.current_qty += stock_quantity
                stk.available_qty = stk.current_qty - stk.reserved_qty
                if itm.unit_price > 0:
                    stk.valuation_rate = itm.unit_price / conversion_factor
                rate = stk.valuation_rate
                qty_after = stk.current_qty
            else:
                stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=itm.item_id,
                    warehouse_id=line_warehouse_id,
                    current_qty=stock_quantity,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=stock_quantity,
                    valuation_rate=itm.unit_price / conversion_factor,
                )
                db.add(stk)
                rate = itm.unit_price / conversion_factor
                qty_after = stock_quantity

            sle = StockLedgerEntry(
                tenant_id=tenant_id,
                posting_datetime=datetime.now(UTC),
                item_id=itm.item_id,
                warehouse_id=line_warehouse_id,
                actual_qty=stock_quantity,
                qty_after_transaction=qty_after,
                valuation_rate=rate,
                stock_value_difference=stock_quantity * rate,
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

    po: PurchaseOrder | None = None
    if req.po_id:
        po = await db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_id == req.po_id, PurchaseOrder.tenant_id == tenant_id).with_for_update())
        if po is None or po.supplier_id != req.supplier_id:
            raise HTTPException(status_code=404, detail="Purchase order not found for this supplier and workspace.")
        if po.status not in {"SUBMITTED", "PARTIALLY_RECEIVED", "COMPLETED"}:
            raise HTTPException(status_code=409, detail="Supplier invoices can only be matched to a submitted purchase order.")
        if req.currency.upper() != po.currency.upper():
            raise HTTPException(status_code=422, detail="Supplier invoice currency must match the linked purchase order currency.")
        settings = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
        tolerance = settings.over_billing_percentage if settings else Decimal("0")
        allowed_subtotal = po.subtotal * (Decimal("1") + tolerance / Decimal("100"))
        if req.subtotal > allowed_subtotal:
            raise HTTPException(status_code=409, detail=f"Invoice subtotal exceeds the purchase-order over-billing tolerance ({tolerance}%).")
    invoice_tax_template_id = req.purchase_tax_template_id or (po.purchase_tax_template_id if po else None)
    if req.due_date and req.due_date < req.invoice_date:
        raise HTTPException(status_code=422, detail="Invoice due date cannot precede invoice date.")
    inv = SupplierInvoice(
        tenant_id=tenant_id,
        invoice_number=req.invoice_number,
        supplier_id=req.supplier_id,
        po_id=req.po_id,
        grn_id=grn_id,
        invoice_date=req.invoice_date,
        due_date=req.due_date or (req.invoice_date + timedelta(days=supplier.payment_terms_days)),
        currency=req.currency,
        subtotal=req.subtotal,
        tax_amount=Decimal("0"),
        total_amount=req.subtotal,
        purchase_tax_template_id=invoice_tax_template_id,
        matching_status="UNMATCHED",
        variance_percentage=Decimal("0.0000"),
    )
    db.add(inv)
    await db.flush()

    from erp.db.models.inventory import Item

    po_items_by_id: dict[uuid.UUID, PurchaseOrderItem] = {}
    document_discount_by_po_item: dict[uuid.UUID, Decimal] = {}
    if req.po_id:
        po_items_by_id = {
            row.item_line_id: row
            for row in (await db.scalars(select(PurchaseOrderItem).where(
                PurchaseOrderItem.tenant_id == tenant_id,
                PurchaseOrderItem.po_id == req.po_id,
            ))).all()
        }
        if po:
            line_discount_total = sum((line.discount_amount for line in po_items_by_id.values()), Decimal("0"))
            document_discount = max(Decimal("0"), po.discount_amount - line_discount_total)
            discountable = [line for line in po_items_by_id.values() if line.quantity * line.unit_price > 0]
            total_basis = sum((line.quantity * line.unit_price for line in discountable), Decimal("0"))
            remaining_doc_discount = document_discount
            for index, line in enumerate(sorted(discountable, key=lambda row: str(row.item_line_id))):
                if index == len(discountable) - 1:
                    allocated = remaining_doc_discount
                else:
                    allocated = (document_discount * line.quantity * line.unit_price / total_basis).quantize(Decimal("0.0001"))
                    remaining_doc_discount -= allocated
                document_discount_by_po_item[line.item_line_id] = allocated
    grn_items_by_id: dict[uuid.UUID, GoodsReceiptNoteItem] = {}
    if grn_id:
        grn_items_by_id = {
            row.grn_item_id: row
            for row in (await db.scalars(select(GoodsReceiptNoteItem).where(
                GoodsReceiptNoteItem.tenant_id == tenant_id,
                GoodsReceiptNoteItem.grn_id == grn_id,
            ))).all()
        }

    calculated_subtotal = Decimal("0")
    invoiced_quantity = Decimal("0")
    if req.items:
        billed_in_request: dict[uuid.UUID, Decimal] = {}
        discount_in_request: dict[uuid.UUID, Decimal] = {}
        allowance_by_line: dict[uuid.UUID, Decimal] = {}
        billed_before_by_line: dict[uuid.UUID, Decimal] = {}
        for itm in req.items:
            resolved_item_id = itm.item_id
            if resolved_item_id is None:
                resolved_item_id = await db.scalar(select(Item.item_id).where(
                    Item.tenant_id == tenant_id, Item.item_code == itm.item_code,
                ))
            elif await db.scalar(select(Item.item_id).where(
                Item.tenant_id == tenant_id, Item.item_id == resolved_item_id,
            )) is None:
                raise HTTPException(status_code=422, detail="Invoice item must belong to this workspace.")
            po_item = po_items_by_id.get(itm.po_item_id) if itm.po_item_id else None
            grn_item = grn_items_by_id.get(itm.grn_item_id) if itm.grn_item_id else None
            if itm.po_item_id and po_item is None:
                raise HTTPException(status_code=422, detail="Purchase-order line must belong to this invoice's purchase order and workspace.")
            if itm.grn_item_id and grn_item is None:
                raise HTTPException(status_code=422, detail="Receipt line must belong to this invoice's receipt and workspace.")
            if grn_item and po_item and grn_item.po_item_id != po_item.item_line_id:
                raise HTTPException(status_code=422, detail="Receipt line and purchase-order line do not belong to the same procurement chain.")
            if po_item and resolved_item_id != po_item.item_id:
                raise HTTPException(status_code=422, detail="Invoice item does not match the selected purchase-order line.")
            if grn_item and resolved_item_id != grn_item.item_id:
                raise HTTPException(status_code=422, detail="Invoice item does not match the selected goods-receipt line.")
            if req.po_id and po_item is None:
                possible = [row for row in po_items_by_id.values() if row.item_id == resolved_item_id]
                if len(possible) == 1:
                    po_item = possible[0]
                elif len(possible) > 1:
                    raise HTTPException(status_code=422, detail="Invoice item matches multiple purchase-order lines; provide po_item_id to disambiguate.")
                else:
                    raise HTTPException(status_code=422, detail="Invoice item must match a line on the linked purchase order.")
            if po_item:
                itm.po_item_id = po_item.item_line_id
                already_billed = await db.scalar(select(func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0)).join(
                    SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id,
                ).where(
                    SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == req.po_id,
                    SupplierInvoice.status != "CANCELLED", SupplierInvoiceItem.tenant_id == tenant_id,
                    SupplierInvoiceItem.po_item_id == po_item.item_line_id,
                ))
                billed_before_by_line[po_item.item_line_id] = Decimal(str(already_billed or 0))
                setting = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
                tolerance_pct = setting.over_billing_percentage if setting else Decimal("0")
                allowance_by_line[po_item.item_line_id] = po_item.quantity * (Decimal("1") + tolerance_pct / Decimal("100"))
                prior_request_qty = billed_in_request.get(po_item.item_line_id, Decimal("0"))
                billed_in_request[po_item.item_line_id] = prior_request_qty + itm.quantity
                if billed_before_by_line[po_item.item_line_id] + billed_in_request[po_item.item_line_id] > allowance_by_line[po_item.item_line_id]:
                    raise HTTPException(status_code=409, detail="Invoice quantity exceeds the purchase-order line's remaining billable quantity.")
                prior_discount = await db.scalar(select(func.coalesce(func.sum(SupplierInvoiceItem.discount_amount), 0)).join(
                    SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id,
                ).where(
                    SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == req.po_id,
                    SupplierInvoice.status != "CANCELLED", SupplierInvoiceItem.tenant_id == tenant_id,
                    SupplierInvoiceItem.po_item_id == po_item.item_line_id,
                ))
                allowed_discount = po_item.discount_amount + document_discount_by_po_item.get(po_item.item_line_id, Decimal("0"))
                pending_discount = discount_in_request.get(po_item.item_line_id, Decimal("0"))
                remaining_discount = max(Decimal("0"), allowed_discount - Decimal(str(prior_discount or 0)) - pending_discount)
                remaining_qty = max(Decimal("0"), po_item.quantity - billed_before_by_line[po_item.item_line_id] - prior_request_qty)
                discountable_qty = min(itm.quantity, remaining_qty)
                line_discount = (remaining_discount * discountable_qty / remaining_qty).quantize(Decimal("0.0001")) if remaining_qty else Decimal("0")
                discount_in_request[po_item.item_line_id] = pending_discount + line_discount
            else:
                line_discount = Decimal("0")
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
                line_total=itm.quantity * itm.unit_price - line_discount,
                discount_amount=line_discount,
                po_item_id=po_item.item_line_id if po_item else None,
                grn_item_id=grn_item.grn_item_id if grn_item else None,
            )
            db.add(inv_item)
            calculated_subtotal += inv_item.line_total
            invoiced_quantity += itm.quantity
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
        setting = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
        tolerance_pct = setting.over_billing_percentage if setting else Decimal("0")
        calculated_subtotal = Decimal("0")
        for po_item, code in po_items:
            billed_before = await db.scalar(select(func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0)).join(
                SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id,
            ).where(
                SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == req.po_id,
                SupplierInvoice.matching_status != "CANCELLED", SupplierInvoiceItem.tenant_id == tenant_id,
                SupplierInvoiceItem.po_item_id == po_item.item_line_id,
            ))
            remaining = max(Decimal("0"), po_item.quantity * (Decimal("1") + tolerance_pct / Decimal("100")) - Decimal(str(billed_before or 0)))
            if remaining <= 0:
                continue
            prior_discount = await db.scalar(select(func.coalesce(func.sum(SupplierInvoiceItem.discount_amount), 0)).join(
                SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id,
            ).where(
                SupplierInvoice.tenant_id == tenant_id, SupplierInvoice.po_id == req.po_id,
                SupplierInvoice.matching_status != "CANCELLED", SupplierInvoiceItem.tenant_id == tenant_id,
                SupplierInvoiceItem.po_item_id == po_item.item_line_id,
            ))
            full_remaining_qty = max(Decimal("0"), po_item.quantity - Decimal(str(billed_before or 0)))
            allowed_discount = po_item.discount_amount + document_discount_by_po_item.get(po_item.item_line_id, Decimal("0"))
            remaining_discount = max(Decimal("0"), allowed_discount - Decimal(str(prior_discount or 0)))
            discountable_qty = min(remaining, full_remaining_qty)
            line_discount = (remaining_discount * discountable_qty / full_remaining_qty).quantize(Decimal("0.0001")) if full_remaining_qty else Decimal("0")
            calculated_subtotal += remaining * po_item.unit_price - line_discount
            invoiced_quantity += remaining
            inv_item = SupplierInvoiceItem(
                tenant_id=tenant_id,
                invoice_id=inv.invoice_id,
                item_id=po_item.item_id,
                item_code=code,
                quantity=remaining,
                unit_price=po_item.unit_price,
                line_total=remaining * po_item.unit_price - line_discount,
                discount_amount=line_discount,
                po_item_id=po_item.item_line_id,
            )
            db.add(inv_item)
        if calculated_subtotal != req.subtotal:
            raise HTTPException(status_code=409, detail=f"Invoice subtotal must match the remaining purchase-order lines ({calculated_subtotal}).")

    if req.items and calculated_subtotal != req.subtotal:
        raise HTTPException(status_code=409, detail=f"Invoice subtotal must match the invoice lines ({calculated_subtotal}).")
    if not req.items and not req.po_id:
        calculated_subtotal = req.subtotal

    if req.purchase_tax_template_id:
        tax_amount, total_amount, tax_snapshot = await _calculate_purchase_tax_snapshot(
            db, tenant_id=tenant_id, template_id=req.purchase_tax_template_id,
            net_total=calculated_subtotal, total_quantity=invoiced_quantity,
        )
    elif po and po.purchase_tax_template_id:
        if not po.tax_snapshot:
            raise HTTPException(status_code=409, detail="The linked purchase order tax snapshot is incomplete; select a purchase tax template explicitly.")
        tax_inputs = _tax_inputs_from_snapshot(po.tax_snapshot)
        try:
            tax_result = calculate_tax_rows(calculated_subtotal, invoiced_quantity, tax_inputs)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        tax_amount = tax_result.tax_total
        tax_snapshot = [{
            "row_id": row.row_id, "charge_type": row.charge_type,
            "description": row.description, "account_head": row.account_head,
            "rate": str(next(tax.rate for tax in tax_inputs if tax.row_id == row.row_id)),
            "reference_row": next(tax.reference_row for tax in tax_inputs if tax.row_id == row.row_id),
            "actual_amount": str(next(tax.actual_amount for tax in tax_inputs if tax.row_id == row.row_id)) if next(tax.actual_amount for tax in tax_inputs if tax.row_id == row.row_id) is not None else None,
            "calculation_base": str(row.calculation_base), "amount": str(row.amount),
            "running_total": str(row.running_total), "included_in_rate": row.included_in_rate,
            "add_deduct": row.add_deduct, "consider_for_valuation": row.consider_for_valuation,
            "source_template_id": str(po.purchase_tax_template_id),
        } for row in tax_result.rows]
        total_amount = total_from_tax_snapshot(calculated_subtotal, tax_snapshot)
    else:
        tax_amount = Decimal("0")
        total_amount = calculated_subtotal
        tax_snapshot = None
        if req.tax_amount:
            raise HTTPException(status_code=422, detail="Tax amounts must be calculated from a purchase tax template, not supplied by the client.")

    if req.tax_amount and req.tax_amount != tax_amount:
        raise HTTPException(status_code=422, detail="Client tax amount does not match the calculated invoice tax.")
    if total_amount < 0:
        raise HTTPException(status_code=422, detail="Invoice total cannot be negative after taxes and deductions.")
    inv.subtotal = calculated_subtotal
    inv.tax_amount = tax_amount
    inv.total_amount = total_amount
    inv.tax_snapshot = tax_snapshot

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
