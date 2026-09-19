import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
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
from erp.db.models.inventory import StockLedgerEntry, StockLevel, Warehouse
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

router = APIRouter(prefix="/commercial", tags=["Commercial & Dynamic Pricing Agent"])


class CreateCustomerRequest(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    credit_limit: Decimal = Decimal("50000.00")


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
    quantity: Decimal
    unit_price: Decimal


class ConvertQuoteToOrderRequest(BaseModel):
    order_number: str | None = None
    delivery_date: date | None = None
    items: list[QuoteItemSpec] = Field(default_factory=list)
    warehouse_id: uuid.UUID | None = None


class FulfillOrderRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None
    delivery_date: date | None = None


class CreateSalesInvoiceRequest(BaseModel):
    invoice_number: str | None = None
    due_date: date | None = None


@router.post("/quotes/{quotation_id}/convert-to-order", status_code=status.HTTP_201_CREATED, summary="Convert quotation to sales order and reserve stock")
async def convert_quote_to_order(
    quotation_id: uuid.UUID,
    req: ConvertQuoteToOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Converts approved quotation into a Sales Order and allocates/reserves stock in inventory."""
    quote = (
        await db.execute(
            select(SalesQuotation).where(
                SalesQuotation.tenant_id == tenant_id,
                SalesQuotation.quotation_id == quotation_id,
            )
        )
    ).scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found.")

    quote.status = "ACCEPTED"
    order_num = req.order_number or f"SO-{quote.quotation_number.replace('QT-', '')}"

    # Calculate total
    total_amt = sum(it.quantity * it.unit_price for it in req.items) if req.items else quote.total_amount

    order = SalesOrder(
        tenant_id=tenant_id,
        order_number=order_num,
        customer_id=quote.customer_id,
        order_date=date.today(),
        delivery_date=req.delivery_date or quote.valid_until,
        total_amount=total_amt,
        status="CONFIRMED",
    )
    db.add(order)
    await db.flush()

    # Get default warehouse if not specified
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

    # Add items and update StockLevel.reserved_qty
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

        if wh_id:
            stk = (
                await db.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == it.item_id,
                        StockLevel.warehouse_id == wh_id,
                    )
                )
            ).scalar_one_or_none()

            if stk:
                stk.reserved_qty += it.quantity
                stk.available_qty = stk.current_qty - stk.reserved_qty
            else:
                stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=it.item_id,
                    warehouse_id=wh_id,
                    current_qty=Decimal("0.0000"),
                    reserved_qty=it.quantity,
                    available_qty=-it.quantity,
                    valuation_rate=it.unit_price,
                )
                db.add(stk)

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
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")

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
            if stk.is_quarantined:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot fulfill order: Stock for item '{itm.item_id}' is QUARANTINED due to quality hold.",
                )
            stk.current_qty -= itm.quantity
            stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - itm.quantity)
            stk.available_qty = stk.current_qty - stk.reserved_qty
            rate = stk.valuation_rate
            qty_after = stk.current_qty

        else:
            rate = itm.unit_price
            qty_after = -itm.quantity

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
    )
    dn = (await db.execute(stmt)).scalar_one_or_none()
    if not dn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery note not found.")

    order = (
        await db.execute(
            select(SalesOrder).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.order_id == dn.order_id,
            )
        )
    ).scalar_one_or_none()

    total_amt = order.total_amount if order else Decimal("0.0000")
    inv_number = req.invoice_number or f"INV-{dn.delivery_note_number.replace('DN-', '')}"

    invoice = SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=inv_number,
        customer_id=dn.customer_id,
        order_id=dn.order_id,
        delivery_note_id=dn.delivery_note_id,
        invoice_date=date.today(),
        due_date=req.due_date or date.today(),
        currency="USD",
        subtotal=total_amt,
        tax_amount=Decimal("0.0000"),
        total_amount=total_amt,
        status="ISSUED",
    )
    db.add(invoice)
    await db.flush()

    for itm in dn.items:
        sinv_item = SalesInvoiceItem(
            tenant_id=tenant_id,
            invoice_id=invoice.invoice_id,
            item_id=itm.item_id,
            quantity=itm.quantity,
            unit_price=total_amt / max(itm.quantity, Decimal("1.0000")),
            line_total=total_amt,
        )
        db.add(sinv_item)

    # Post to General Ledger via Deterministic Ledger Engine
    # Debit: 1200-AR-CUSTOMERS, Credit: 4000-SALES-REVENUE
    from erp.ledger.engine import TransactionProposal, ledger_engine
    from erp.ledger.invariants import LedgerLineProposal

    entries = [
        LedgerLineProposal(
            account_code="1200-AR-CUSTOMERS",
            cost_center="SALES-GLOBAL",
            debit_amount=total_amt,
            credit_amount=Decimal("0.0000"),
            currency="USD",
        ),
        LedgerLineProposal(
            account_code="4000-SALES-REVENUE",
            cost_center="SALES-GLOBAL",
            debit_amount=Decimal("0.0000"),
            credit_amount=total_amt,
            currency="USD",
        ),
    ]

    proposal = TransactionProposal(
        tenant_id=tenant_id,
        posting_date=invoice.invoice_date,
        currency="USD",
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
