import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep, require_roles
from erp.commercial.bom_cost_rollup import (
    BOMCostRollupResult,
    bom_rollup_engine,
)
from erp.commercial.pdf_generator import (
    QuotationData,
    pdf_generator,
)
from erp.commercial.pricing_engine import (
    DynamicPricingEvaluation,
    pricing_engine,
)
from erp.commercial.quote_invalidator import (
    QuoteInvalidationNotice,
    quote_invalidator,
)
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.sales import (
    Customer,
    DeliveryNote,
    DeliveryNoteItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
)
from erp.db.models.tenant import Tenant
from erp.db.models.user import User
from erp.ledger.sales_posting import (
    SalesPostingConfigurationError,
    resolve_sales_posting_configuration,
)

router = APIRouter(prefix="/commercial", tags=["Commercial & Dynamic Pricing Agent"])
controller_review_dep = require_roles("CONTROLLER")


class CreateCustomerRequest(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    credit_limit: Decimal = Decimal("50000.00")
    payment_terms_days: int = Field(default=30, ge=0, le=3650)


class CreateSalesQuoteRequest(BaseModel):
    quotation_number: str = Field(..., min_length=2, max_length=64)
    customer_id: uuid.UUID
    quotation_date: date
    valid_until: date
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.00")
    contribution_margin_pct: Decimal = Decimal("25.00")


@router.get("/customers", summary="List customers")
async def list_customers(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns commercial customers for the tenant."""
    stmt = (
        select(Customer)
        .where(Customer.tenant_id == tenant_id)
        .order_by(Customer.customer_name.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/customers", status_code=status.HTTP_201_CREATED, summary="Create customer")
async def create_customer(req: CreateCustomerRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Adds a new commercial customer account."""
    existing = (
        await db.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id, Customer.customer_code == req.customer_code
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer '{req.customer_code}' already exists.",
        )

    cust = Customer(
        tenant_id=tenant_id,
        customer_code=req.customer_code,
        customer_name=req.customer_name,
        email=req.email,
        credit_limit=req.credit_limit,
        payment_terms_days=req.payment_terms_days,
        lifetime_value=Decimal("0.0000"),
        is_active=True,
    )
    db.add(cust)
    await db.flush()
    return cust


@router.get("/quotes", summary="List sales quotations")
async def list_sales_quotes(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns dynamic commercial quotations for the tenant."""
    stmt = (
        select(SalesQuotation)
        .where(SalesQuotation.tenant_id == tenant_id)
        .order_by(SalesQuotation.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/quotes", status_code=status.HTTP_201_CREATED, summary="Create sales quotation")
async def create_sales_quote(
    req: CreateSalesQuoteRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Records a new evaluated commercial sales quotation."""
    total = req.subtotal + req.tax_amount
    quote = SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=req.quotation_number,
        customer_id=req.customer_id,
        quotation_date=req.quotation_date,
        valid_until=req.valid_until,
        subtotal=req.subtotal,
        tax_amount=req.tax_amount,
        total_amount=total,
        contribution_margin_pct=req.contribution_margin_pct,
        status="OFFICIAL",
    )
    db.add(quote)
    await db.flush()
    return quote


class QuoteItemSpec(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class ConvertQuoteToOrderRequest(BaseModel):
    order_number: str | None = Field(default=None, min_length=2, max_length=64)
    delivery_date: date | None = None
    items: list[QuoteItemSpec] = Field(min_length=1, max_length=100)
    warehouse_id: uuid.UUID | None = None


class FulfillOrderRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None
    delivery_date: date | None = None


class ConfirmSalesOrderRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None


class CreateSalesInvoiceRequest(BaseModel):
    invoice_number: str | None = None
    due_date: date | None = None


@router.post("/quotes/{quotation_id}/convert-to-order", status_code=status.HTTP_201_CREATED, summary="Convert quotation to sales order and reserve stock")
async def convert_quote_to_order(
    quotation_id: uuid.UUID,
    req: ConvertQuoteToOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reviewer: User = controller_review_dep,
):
    """Convert an unexpired quote once, only when every line can be reserved safely."""
    quote = (
        await db.execute(
            select(SalesQuotation)
            .where(
                SalesQuotation.tenant_id == tenant_id,
                SalesQuotation.quotation_id == quotation_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found.")
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")

    if quote.status not in {"OFFICIAL", "SENT"} or quote.valid_until < date.today():
        raise HTTPException(status_code=409, detail="Quotation is not in an orderable status or has expired.")
    customer = (
        await db.execute(
            select(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.customer_id == quote.customer_id,
                Customer.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=409, detail="Quotation customer is no longer active in this tenant.")
    order_num = req.order_number or f"SO-{quote.quotation_number.replace('QT-', '')}"
    if len({line.item_id for line in req.items}) != len(req.items):
        raise HTTPException(status_code=422, detail="Combine duplicate item lines before converting the quote.")
    duplicate = (
        await db.execute(
            select(SalesOrder.order_id).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.order_number == order_num,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="Sales order number already exists for this tenant.")

    item_ids = [line.item_id for line in req.items]
    items = (
        await db.execute(
            select(Item)
            .where(
                Item.tenant_id == tenant_id,
                Item.item_id.in_(item_ids),
                Item.is_active.is_(True),
                Item.is_sales_item.is_(True),
            )
            .with_for_update()
        )
    ).scalars().all()
    if len(items) != len(item_ids):
        raise HTTPException(status_code=422, detail="Every order line must reference an active tenant-owned sales item.")
    total_amt = sum((line.quantity * line.unit_price for line in req.items), Decimal("0.0000"))
    if total_amt <= 0 or total_amt >= Decimal("100000000000000"):
        raise HTTPException(status_code=422, detail="Order total is outside the supported monetary range.")
    if total_amt != quote.total_amount:
        raise HTTPException(status_code=409, detail="Order line total must match the accepted quotation total.")
    open_invoice_total = (
        await db.execute(
            select(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.customer_id == customer.customer_id,
                SalesInvoice.status.notin__(("PAID", "CANCELLED")),
            )
        )
    ).scalar_one()
    other_open_order_total = (
        await db.execute(
            select(func.coalesce(func.sum(SalesOrder.total_amount), 0)).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.customer_id == customer.customer_id,
                SalesOrder.status.in__(("PENDING_CONFIRMATION", "CONFIRMED", "BACKORDERED")),
            )
        )
    ).scalar_one()
    credit_exposure = Decimal(str(open_invoice_total)) + Decimal(str(other_open_order_total)) + total_amt
    if credit_exposure > customer.credit_limit:
        raise HTTPException(status_code=409, detail="Order exceeds available customer credit; finance review is required.")
    if req.delivery_date and req.delivery_date < date.today():
        raise HTTPException(status_code=422, detail="Delivery date cannot be in the past.")

    warehouse_query = select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.is_active.is_(True),
        Warehouse.is_quarantine.is_(False),
    )
    if req.warehouse_id:
        warehouse_query = warehouse_query.where(Warehouse.warehouse_id == req.warehouse_id)
    warehouses = (await db.execute(warehouse_query.order_by(Warehouse.warehouse_code))).scalars().all()
    chosen_warehouse = None
    reservation_rows: list[tuple[StockLevel, Decimal]] = []
    for warehouse in warehouses:
        stocks = (
            await db.execute(
                select(StockLevel)
                .where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.warehouse_id == warehouse.warehouse_id,
                    StockLevel.item_id.in_(item_ids),
                )
                .order_by(StockLevel.item_id)
                .with_for_update()
            )
        ).scalars().all()
        stock_by_item = {stock.item_id: stock for stock in stocks}
        candidate: list[tuple[StockLevel, Decimal]] = []
        for line in sorted(req.items, key=lambda value: str(value.item_id)):
            stock = stock_by_item.get(line.item_id)
            if stock is None or stock.is_quarantined or stock.current_qty - stock.reserved_qty < line.quantity:
                break
            candidate.append((stock, line.quantity))
        if len(candidate) == len(req.items):
            chosen_warehouse = warehouse
            reservation_rows = candidate
            break
    if chosen_warehouse is None:
        raise HTTPException(status_code=409, detail="No active warehouse can reserve every quote line from available, unquarantined stock.")

    order = SalesOrder(
        tenant_id=tenant_id,
        order_number=order_num,
        customer_id=quote.customer_id,
        order_date=date.today(),
        delivery_date=req.delivery_date or quote.valid_until,
        total_amount=total_amt,
        status="CONFIRMED",
        fulfillment_warehouse_id=chosen_warehouse.warehouse_id,
    )
    db.add(order)
    await db.flush()
    for it in req.items:
        so_item = SalesOrderItem(
            tenant_id=tenant_id,
            order_id=order.order_id,
            item_id=it.item_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            line_total=it.quantity * it.unit_price,
        )
        db.add(so_item)
    for stock, quantity in reservation_rows:
        stock.reserved_qty += quantity
        stock.available_qty = stock.current_qty - stock.reserved_qty
    quote.status = "ACCEPTED"
    await db.flush()
    return order


@router.get("/orders", summary="List commercial sales orders")
async def list_sales_orders(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists sales orders for the tenant with items."""
    stmt = (
        select(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .where(SalesOrder.tenant_id == tenant_id)
        .order_by(SalesOrder.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/orders/{order_id}/confirm", summary="Confirm a pending order and reserve available stock")
async def confirm_pending_sales_order(
    order_id: uuid.UUID,
    req: ConfirmSalesOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reviewer: User = controller_review_dep,
):
    """Confirm a reviewed draft only when every line can be reserved from one warehouse."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    order = (
        await db.execute(
            select(SalesOrder)
            .where(SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found.")
    if order.status == "CONFIRMED" and order.fulfillment_warehouse_id:
        return {
            "order_id": str(order.order_id),
            "status": order.status,
            "warehouse_id": str(order.fulfillment_warehouse_id),
            "already_confirmed": True,
        }
    if order.status != "PENDING_CONFIRMATION":
        raise HTTPException(status_code=409, detail="Only pending-confirmation orders can be confirmed.")

    customer = (
        await db.execute(
            select(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.customer_id == order.customer_id,
                Customer.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=409, detail="Order customer is no longer active in this tenant.")
    open_invoice_total = (
        await db.execute(
            select(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.customer_id == customer.customer_id,
                SalesInvoice.status.notin_(("PAID", "CANCELLED")),
            )
        )
    ).scalar_one()
    other_open_order_total = (
        await db.execute(
            select(func.coalesce(func.sum(SalesOrder.total_amount), 0)).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.customer_id == customer.customer_id,
                SalesOrder.order_id != order.order_id,
                SalesOrder.status.in_(("PENDING_CONFIRMATION", "CONFIRMED", "BACKORDERED")),
            )
        )
    ).scalar_one()
    credit_exposure = Decimal(str(open_invoice_total)) + Decimal(str(other_open_order_total)) + order.total_amount
    if credit_exposure > customer.credit_limit:
        raise HTTPException(status_code=409, detail="Order exceeds available customer credit; finance review is required.")

    lines = (
        await db.execute(
            select(SalesOrderItem)
            .where(SalesOrderItem.tenant_id == tenant_id, SalesOrderItem.order_id == order.order_id)
            .order_by(SalesOrderItem.item_id)
        )
    ).scalars().all()
    if not lines:
        raise HTTPException(status_code=409, detail="Sales order has no items and cannot be confirmed.")

    warehouse_query = select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.is_active.is_(True),
        Warehouse.is_quarantine.is_(False),
    )
    if req.warehouse_id:
        warehouse_query = warehouse_query.where(Warehouse.warehouse_id == req.warehouse_id)
    warehouses = (await db.execute(warehouse_query.order_by(Warehouse.warehouse_code))).scalars().all()
    reservations: list[tuple[StockLevel, Decimal]] | None = None
    chosen_warehouse: Warehouse | None = None
    for warehouse in warehouses:
        stocks = (
            await db.execute(
                select(StockLevel)
                .where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.warehouse_id == warehouse.warehouse_id,
                    StockLevel.item_id.in_([line.item_id for line in lines]),
                )
                .order_by(StockLevel.item_id)
                .with_for_update()
            )
        ).scalars().all()
        stock_by_item = {stock.item_id: stock for stock in stocks}
        candidate: list[tuple[StockLevel, Decimal]] = []
        for line in lines:
            stock = stock_by_item.get(line.item_id)
            if stock is None or stock.is_quarantined:
                break
            available = stock.current_qty - stock.reserved_qty
            if available < line.quantity:
                break
            candidate.append((stock, line.quantity))
        if len(candidate) == len(lines):
            reservations = candidate
            chosen_warehouse = warehouse
            break
    if reservations is None or chosen_warehouse is None:
        raise HTTPException(status_code=409, detail="No selected active warehouse has unquarantined stock for every order line.")

    for stock, quantity in reservations:
        stock.reserved_qty += quantity
        stock.available_qty = stock.current_qty - stock.reserved_qty
    order.fulfillment_warehouse_id = chosen_warehouse.warehouse_id
    order.status = "CONFIRMED"
    await db.flush()
    return {
        "order_id": str(order.order_id),
        "status": order.status,
        "warehouse_id": str(chosen_warehouse.warehouse_id),
        "stock_reserved": True,
    }


@router.post("/orders/{order_id}/fulfill", status_code=status.HTTP_201_CREATED, summary="Fulfill order and generate Delivery Note")
async def fulfill_sales_order(
    order_id: uuid.UUID,
    req: FulfillOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Dispatches order delivery: generates Delivery Note, permanently deducts stock from on-hand, and records Stock Ledger Entry."""
    stmt = (
        select(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .where(
            SalesOrder.tenant_id == tenant_id,
            SalesOrder.order_id == order_id,
        )
        .with_for_update(of=SalesOrder)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")

    if order.status not in {"CONFIRMED", "BACKORDERED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sales order must be confirmed before fulfillment.",
        )

    existing_dn = (
        await db.execute(
            select(DeliveryNote)
            .where(DeliveryNote.tenant_id == tenant_id, DeliveryNote.order_id == order.order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing_dn:
        return existing_dn

    wh_id = order.fulfillment_warehouse_id
    if wh_id and req.warehouse_id and req.warehouse_id != wh_id:
        raise HTTPException(status_code=409, detail="Order stock is reserved at a different warehouse.")
    if not wh_id:
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
        if not wh:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active warehouse found.")
        wh_id = wh.warehouse_id

    order_quantities: dict[uuid.UUID, Decimal] = {}
    for line in order.items:
        order_quantities[line.item_id] = order_quantities.get(line.item_id, Decimal("0.0000")) + line.quantity
    stock_rows = (
        await db.execute(
            select(StockLevel)
            .where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.warehouse_id == wh_id,
                StockLevel.item_id.in_(order_quantities),
            )
            .order_by(StockLevel.item_id)
            .with_for_update()
        )
    ).scalars().all()
    stock_by_item = {stock.item_id: stock for stock in stock_rows}
    for item_id, quantity in order_quantities.items():
        stock = stock_by_item.get(item_id)
        if stock is None or stock.is_quarantined or stock.current_qty < quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Stock for item {item_id} is unavailable, quarantined, or insufficient at the selected warehouse.",
            )
        if order.fulfillment_warehouse_id and stock.reserved_qty < quantity:
            raise HTTPException(status_code=409, detail=f"Reserved stock for item {item_id} is no longer available.")

    dn_number = f"DN-{order.order_number}"
    dn = DeliveryNote(
        tenant_id=tenant_id,
        delivery_note_number=dn_number,
        order_id=order.order_id,
        customer_id=order.customer_id,
        delivery_date=req.delivery_date or date.today(),
        status="COMPLETED",
    )
    db.add(dn)
    await db.flush()

    from datetime import UTC, datetime

    for itm in order.items:
        dn_item = DeliveryNoteItem(
            tenant_id=tenant_id,
            delivery_note_id=dn.delivery_note_id,
            order_item_id=itm.order_item_id,
            item_id=itm.item_id,
            warehouse_id=wh_id,
            quantity=itm.quantity,
        )
        db.add(dn_item)

        stk = stock_by_item[itm.item_id]
        stk.current_qty -= itm.quantity
        stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - itm.quantity)
        stk.available_qty = stk.current_qty - stk.reserved_qty
        rate = stk.valuation_rate
        qty_after = stk.current_qty

        sle = StockLedgerEntry(
            tenant_id=tenant_id,
            posting_datetime=datetime.now(UTC),
            item_id=itm.item_id,
            warehouse_id=wh_id,
            actual_qty=-itm.quantity,
            qty_after_transaction=qty_after,
            valuation_rate=rate,
            stock_value_difference=-itm.quantity * rate,
            source_document_type="DELIVERY_NOTE",
            source_document_id=dn.delivery_note_id,
        )
        db.add(sle)

    order.status = "DELIVERED"
    await db.flush()
    return dn


@router.post("/delivery-notes/{delivery_note_id}/create-invoice", status_code=status.HTTP_201_CREATED, summary="Create sales invoice and post to General Ledger")
async def create_sales_invoice_from_delivery(
    delivery_note_id: uuid.UUID,
    req: CreateSalesInvoiceRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Generates Sales Invoice from Delivery Note and commits double-entry journal entry: Dr AR-Customers / Cr Sales Revenue."""
    stmt = (
        select(DeliveryNote)
        .options(selectinload(DeliveryNote.items))
        .where(
            DeliveryNote.tenant_id == tenant_id,
            DeliveryNote.delivery_note_id == delivery_note_id,
        )
        .with_for_update(of=DeliveryNote)
    )
    dn = (await db.execute(stmt)).scalar_one_or_none()
    if not dn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery note not found.")

    existing_invoice = (
        await db.execute(
            select(SalesInvoice)
            .where(
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.delivery_note_id == dn.delivery_note_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing_invoice:
        journal_entries = (
            await db.execute(
                select(GeneralLedgerEntry.entry_id).where(
                    GeneralLedgerEntry.tenant_id == tenant_id,
                    GeneralLedgerEntry.source_document_type == "SALES_INVOICE",
                    GeneralLedgerEntry.source_document_id == existing_invoice.invoice_id,
                )
            )
        ).scalars().all()
        if journal_entries:
            return existing_invoice
        raise HTTPException(
            status_code=409,
            detail="An invoice exists without a verifiable ledger posting; finance reconciliation is required.",
        )

    order = (
        await db.execute(
            select(SalesOrder)
            .options(selectinload(SalesOrder.items))
            .where(SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == dn.order_id)
            .with_for_update(of=SalesOrder)
        )
    ).scalar_one_or_none()

    if order is None or order.status != "DELIVERED":
        raise HTTPException(status_code=409, detail="A delivered sales order is required before invoicing.")
    total_amt = order.total_amount
    customer = (
        await db.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.customer_id == order.customer_id,
                Customer.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=409, detail="Active tenant customer is required for invoicing.")
    inv_number = req.invoice_number or f"INV-{dn.delivery_note_number.replace('DN-', '')}"
    invoice_date = date.today()
    due_date = req.due_date or (invoice_date + timedelta(days=customer.payment_terms_days))
    if due_date < invoice_date:
        raise HTTPException(status_code=422, detail="Invoice due date cannot precede its invoice date.")

    tenant_currency = (
        await db.execute(select(Tenant.currency).where(Tenant.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not tenant_currency:
        raise HTTPException(status_code=409, detail="Tenant currency configuration is required before invoicing.")
    invoice = SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=inv_number,
        customer_id=dn.customer_id,
        order_id=dn.order_id,
        delivery_note_id=dn.delivery_note_id,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=tenant_currency,
        subtotal=total_amt,
        tax_amount=Decimal("0.0000"),
        total_amount=total_amt,
        status="ISSUED",
    )
    db.add(invoice)
    await db.flush()

    order_items_by_id = {item.order_item_id: item for item in order.items}
    invoice_line_total = Decimal("0.0000")
    for itm in dn.items:
        order_item = order_items_by_id.get(itm.order_item_id)
        if order_item is None or order_item.item_id != itm.item_id or order_item.quantity != itm.quantity:
            raise HTTPException(status_code=409, detail="Delivery note lines do not match the tenant sales order.")
        line_total = itm.quantity * order_item.unit_price
        invoice_line_total += line_total
        sinv_item = SalesInvoiceItem(
            tenant_id=tenant_id,
            invoice_id=invoice.invoice_id,
            item_id=itm.item_id,
            quantity=itm.quantity,
            unit_price=order_item.unit_price,
            line_total=line_total,
        )
        db.add(sinv_item)

    if invoice_line_total != total_amt:
        raise HTTPException(status_code=409, detail="Invoice lines do not reconcile to the sales order total.")

    # Post through the canonical ledger engine using unambiguous tenant mappings.
    from erp.ledger.engine import TransactionProposal, ledger_engine
    from erp.ledger.invariants import LedgerLineProposal

    try:
        ar_account, revenue_account, cost_center = await resolve_sales_posting_configuration(
            db, tenant_id, tenant_currency
        )
    except SalesPostingConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    entries = [
        LedgerLineProposal(
            account_code=ar_account.account_code,
            cost_center=cost_center.cost_center_code,
            debit_amount=total_amt,
            credit_amount=Decimal("0.0000"),
            currency=tenant_currency,
        ),
        LedgerLineProposal(
            account_code=revenue_account.account_code,
            cost_center=cost_center.cost_center_code,
            debit_amount=Decimal("0.0000"),
            credit_amount=total_amt,
            currency=tenant_currency,
        ),
    ]

    proposal = TransactionProposal(
        tenant_id=tenant_id,
        posting_date=invoice.invoice_date,
        currency=tenant_currency,
        source_document_type="SALES_INVOICE",
        source_document_id=invoice.invoice_id,
        entries=entries,
        human_in_the_loop_approved=False,
        agent_id="REVENUE_CONTROLLER",
        verification_context={"invoice_number": invoice.invoice_number},
    )

    await ledger_engine.commit_transaction(session=db, proposal=proposal)
    await db.flush()
    return invoice



class PricingCalculateRequest(BaseModel):
    sku: str
    bom_material_cost: Decimal
    machine_depreciation: Decimal = Decimal("4.5000")
    direct_labor: Decimal = Decimal("6.0000")
    freight: Decimal = Decimal("1.2500")
    target_markup_multiplier: Decimal = Decimal("1.3500")


class BOMRollupRequest(BaseModel):
    parent_sku: str
    material_deltas: dict[str, tuple[Decimal, Decimal, Decimal]] = Field(
        description="component_sku -> (unit_quantity, old_unit_price, new_unit_price)"
    )


class QuoteInvalidateRequest(BaseModel):
    quote_number: str
    customer_name: str
    sku: str
    current_quoted_price: Decimal
    new_bom_material_cost: Decimal


@router.post("/pricing/calculate", response_model=DynamicPricingEvaluation)
async def calculate_pricing(req: PricingCalculateRequest) -> DynamicPricingEvaluation:
    """Calculates landed cost and defends corporate 22.0% contribution margin floor."""
    try:
        return pricing_engine.calculate_margin_defended_price(
            sku=req.sku,
            bom_material_cost=req.bom_material_cost,
            machine_depreciation=req.machine_depreciation,
            direct_labor=req.direct_labor,
            freight=req.freight,
            target_markup_multiplier=req.target_markup_multiplier,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pricing calculation failed: {e!s}",
        ) from e


@router.post("/bom/rollup", response_model=BOMCostRollupResult)
async def calculate_bom_rollup(req: BOMRollupRequest) -> BOMCostRollupResult:
    """Calculates raw material cost growth across BOM components during supplier price spikes."""
    try:
        return bom_rollup_engine.calculate_bom_cost_delta(
            parent_sku=req.parent_sku,
            material_deltas=req.material_deltas,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BOM rollup calculation failed: {e!s}",
        ) from e


@router.post("/quote/evaluate-invalidation", response_model=QuoteInvalidationNotice)
async def evaluate_quote_invalidation(req: QuoteInvalidateRequest) -> QuoteInvalidationNotice:
    """Evaluates whether raw material price inflation erodes quote margin below the 22% threshold."""
    try:
        return quote_invalidator.evaluate_active_quote(
            quote_number=req.quote_number,
            customer_name=req.customer_name,
            sku=req.sku,
            current_quoted_price=req.current_quoted_price,
            new_bom_material_cost=req.new_bom_material_cost,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quote invalidation evaluation failed: {e!s}",
        ) from e


@router.post("/quote/pdf")
async def generate_quote_pdf(quote: QuotationData):
    """Generates an official commercial PDF quotation document using ReportLab."""
    try:
        pdf_bytes = pdf_generator.generate_pdf(quote)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{quote.quote_number}.pdf"',
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {e!s}",
        ) from e
