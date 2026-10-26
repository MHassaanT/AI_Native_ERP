import uuid
from datetime import UTC, date, datetime, timedelta
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
from erp.db.models.purchasing import DocumentAuditBatch
from erp.db.models.sales import (
    Customer,
    DeliveryNote,
    DeliveryNoteItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
)
from erp.db.models.shared_master import Address, Contact, PriceList, TermsAndConditionsTemplate
from erp.db.models.phase_b import SalesPartner, SalesTeam, ShippingRule
from erp.db.models.billing import SalesTaxesAndChargesTemplate
from erp.db.models.tenant import Tenant
from erp.db.models.user import User
from erp.ledger.sales_posting import (
    SalesPostingConfigurationError,
    resolve_sales_posting_configuration,
)
from erp.workflows.commercial.calculation_service import (
    CalculationLineInput,
    TaxRowInput,
    calculate_tax_rows,
    commercial_calculation_service,
)
from erp.workflows.commercial.sales_team_service import invoice_sales_team_snapshot

router = APIRouter(prefix="/commercial", tags=["Commercial & Dynamic Pricing Agent"])
controller_review_dep = require_roles("CONTROLLER")


class CalculationLineSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    uom_id: uuid.UUID | None = None
    price_list_id: uuid.UUID | None = None


class CalculationTaxRowSchema(BaseModel):
    row_id: int = Field(ge=1)
    charge_type: str
    rate: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    description: str
    account_head: str
    reference_row: int | None = Field(default=None, ge=1)
    actual_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    included_in_rate: bool = False
    add_deduct: str = "ADD"
    consider_for_valuation: bool = False


class CalculationPreviewRequest(BaseModel):
    context: str = Field(pattern="^(BUYING|SELLING|buying|selling)$")
    currency: str = Field(min_length=3, max_length=3)
    price_list_id: uuid.UUID | None = None
    shipping_rule_id: uuid.UUID | None = None
    destination_country: str | None = None
    destination_state: str | None = None
    calculation_date: date | None = None
    lines: list[CalculationLineSchema] = Field(min_length=1, max_length=100)
    tax_rows: list[CalculationTaxRowSchema] = Field(default_factory=list, max_length=100)


@router.post("/calculations/preview", summary="Preview tenant-scoped buying/selling prices and charges")
async def preview_commercial_calculation(req: CalculationPreviewRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        calculation = await commercial_calculation_service.calculate(
            db,
            tenant_id=tenant_id,
            context=req.context,
            currency=req.currency.upper(),
            price_list_id=req.price_list_id,
            shipping_rule_id=req.shipping_rule_id,
            destination_country=req.destination_country,
            destination_state=req.destination_state,
            calculation_date=req.calculation_date,
            lines=[CalculationLineInput(**line.model_dump()) for line in req.lines],
        )
        tax_result = None
        if req.tax_rows:
            tax_inputs = [TaxRowInput(**row.model_dump()) for row in req.tax_rows]
            tax_result = calculate_tax_rows(
                calculation.subtotal + calculation.shipping_charge,
                sum((line.entered_quantity for line in calculation.lines), Decimal("0")),
                tax_inputs,
            )
        return {"calculation": calculation, "tax_calculation": tax_result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CreateCustomerRequest(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    credit_limit: Decimal = Decimal("50000.00")
    payment_terms_days: int = Field(default=30, ge=0, le=3650)


class SalesQuoteLineSpec(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    uom_id: uuid.UUID | None = None
    price_list_id: uuid.UUID | None = None


class CreateSalesQuoteRequest(BaseModel):
    quotation_number: str = Field(..., min_length=2, max_length=64)
    customer_id: uuid.UUID
    quotation_date: date
    valid_until: date
    subtotal: Decimal | None = None
    tax_amount: Decimal = Decimal("0.00")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    price_list_id: uuid.UUID | None = None
    shipping_rule_id: uuid.UUID | None = None
    sales_tax_template_id: uuid.UUID | None = None
    contribution_margin_pct: Decimal = Decimal("25.00")
    items: list[SalesQuoteLineSpec] = Field(default_factory=list, max_length=100)


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
        .options(selectinload(SalesQuotation.items))
        .where(SalesQuotation.tenant_id == tenant_id)
        .order_by(SalesQuotation.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/quotes", status_code=status.HTTP_201_CREATED, summary="Create sales quotation")
async def create_sales_quote(
    req: CreateSalesQuoteRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Records a new evaluated commercial sales quotation."""
    customer_exists = await db.scalar(select(Customer.customer_id).where(
        Customer.tenant_id == tenant_id,
        Customer.customer_id == req.customer_id,
        Customer.is_active.is_(True),
    ))
    if customer_exists is None:
        raise HTTPException(status_code=422, detail="Customer must be active and belong to this workspace.")
    if req.items:
        quote_item_ids = {line.item_id for line in req.items}
        active_items = set((await db.scalars(select(Item.item_id).where(
            Item.tenant_id == tenant_id, Item.item_id.in_(quote_item_ids),
            Item.is_active.is_(True), Item.is_sales_item.is_(True),
        ))).all())
        if active_items != quote_item_ids:
            raise HTTPException(status_code=422, detail="Every quotation line must reference an active sales item in this workspace.")
    if not req.items:
        raise HTTPException(status_code=422, detail="A sales quotation requires persisted line items.")
    tax_template = None
    if req.sales_tax_template_id:
        tax_template = await db.scalar(select(SalesTaxesAndChargesTemplate).options(
            selectinload(SalesTaxesAndChargesTemplate.taxes),
        ).where(
            SalesTaxesAndChargesTemplate.tenant_id == tenant_id,
            SalesTaxesAndChargesTemplate.template_id == req.sales_tax_template_id,
            SalesTaxesAndChargesTemplate.disabled.is_(False),
        ))
        if tax_template is None:
            raise HTTPException(status_code=422, detail="Sales tax template must be active and belong to this workspace.")
    try:
        calculation = await commercial_calculation_service.calculate(
            db, tenant_id=tenant_id, context="SELLING", currency=req.currency.upper(),
            price_list_id=req.price_list_id, shipping_rule_id=req.shipping_rule_id,
            lines=[CalculationLineInput(
                item_id=line.item_id, quantity=line.quantity, unit_price=line.unit_price,
                uom_id=line.uom_id, price_list_id=line.price_list_id,
            ) for line in req.items],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    calculated_main = [line for line in calculation.lines if not line.is_free]
    gross_subtotal = sum((line.base_rate * line.entered_quantity for line in calculated_main), Decimal("0"))
    tax_result = None
    tax_snapshot = None
    if tax_template:
        details = sorted(tax_template.taxes, key=lambda row: row.row_id or 0)
        tax_inputs = []
        prior_row_id = None
        for index, detail in enumerate(details, start=1):
            row_id = detail.row_id or index
            tax_inputs.append(TaxRowInput(
                row_id=row_id, charge_type=detail.charge_type, rate=Decimal(detail.rate),
                description=detail.description, account_head=detail.account_head,
                reference_row=detail.reference_row or (prior_row_id if "Previous Row" in detail.charge_type else None),
                actual_amount=Decimal(detail.rate) if detail.charge_type == "Actual" else None,
                included_in_rate=detail.included_in_rate, add_deduct=detail.add_deduct,
                consider_for_valuation=detail.consider_for_valuation,
            ))
            prior_row_id = row_id
        tax_result = calculate_tax_rows(calculation.subtotal + calculation.shipping_charge,
            sum((line.entered_quantity for line in calculation.lines), Decimal("0")), tax_inputs)
        tax_snapshot = [{
            "row_id": row.row_id,
            "charge_type": row.charge_type,
            "description": row.description,
            "account_head": row.account_head,
            "calculation_base": str(row.calculation_base),
            "amount": str(row.amount),
            "running_total": str(row.running_total),
            "included_in_rate": row.included_in_rate,
            "add_deduct": row.add_deduct,
            "consider_for_valuation": row.consider_for_valuation,
            "source_template_id": str(req.sales_tax_template_id),
        } for row in tax_result.rows]
    elif req.tax_amount:
        raise HTTPException(status_code=422, detail="Tax amount must come from a tenant-owned sales tax template; client-supplied tax totals are not accepted.")
    tax_amount = tax_result.tax_total if tax_result else Decimal("0")
    total = (tax_result.grand_total if tax_result else calculation.subtotal + calculation.shipping_charge)
    quote = SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=req.quotation_number,
        customer_id=req.customer_id,
        quotation_date=req.quotation_date,
        valid_until=req.valid_until,
        subtotal=gross_subtotal,
        tax_amount=tax_amount,
        total_amount=total,
        currency=req.currency.upper(),
        price_list_id=req.price_list_id,
        shipping_rule_id=req.shipping_rule_id,
        sales_tax_template_id=req.sales_tax_template_id,
        tax_snapshot=tax_snapshot,
        discount_amount=calculation.discount_total,
        shipping_charge=calculation.shipping_charge,
        calculation_hash=calculation.calculation_hash,
        contribution_margin_pct=req.contribution_margin_pct,
        status="OFFICIAL",
    )
    db.add(quote)
    await db.flush()
    for calculated in calculation.lines:
        db.add(SalesQuotationItem(
            tenant_id=tenant_id,
            quotation_id=quote.quotation_id,
            item_id=calculated.item_id,
            quantity=calculated.entered_quantity,
            unit_price=calculated.base_rate,
            line_total=calculated.line_total,
            uom_id=calculated.uom_id,
            conversion_factor=calculated.conversion_factor,
            stock_quantity=calculated.stock_quantity,
            price_list_id=calculated.price_list_id,
            item_price_id=calculated.item_price_id,
            price_list_rate=calculated.price_list_rate,
            discount_amount=calculated.discount_amount,
            pricing_rule_id=calculated.pricing_rule_id,
            promotion_id=calculated.promotion_id,
            is_free=calculated.is_free,
        ))
    await db.flush()
    return quote


class QuoteItemSpec(BaseModel):
    item_id: uuid.UUID
    quotation_item_id: uuid.UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class SalesTeamAssignmentInput(BaseModel):
    partner_id: uuid.UUID
    contribution_pct: Decimal = Field(gt=0, le=100, max_digits=7, decimal_places=4)
    commission_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=4)


class ConvertQuoteToOrderRequest(BaseModel):
    order_number: str | None = Field(default=None, min_length=2, max_length=64)
    delivery_date: date | None = None
    items: list[QuoteItemSpec] = Field(min_length=1, max_length=100)
    warehouse_id: uuid.UUID | None = None
    customer_contact_id: uuid.UUID | None = None
    billing_address_id: uuid.UUID | None = None
    shipping_address_id: uuid.UUID | None = None
    terms_template_id: uuid.UUID | None = None
    terms_text: str | None = None
    price_list_id: uuid.UUID | None = None
    shipping_rule_id: uuid.UUID | None = None
    payment_terms: str | None = None
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=0, max_digits=18, decimal_places=8)
    sales_team: list[SalesTeamAssignmentInput] = Field(default_factory=list, max_length=20)


class FulfillOrderItemRequest(BaseModel):
    order_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class FulfillOrderRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None
    delivery_date: date | None = None
    items: list[FulfillOrderItemRequest] | None = Field(default=None, min_length=1, max_length=100)


class ConfirmSalesOrderRequest(BaseModel):
    warehouse_id: uuid.UUID | None = None


class AmendSalesOrderRequest(BaseModel):
    order_number: str = Field(..., min_length=2, max_length=64)


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
            .options(selectinload(SalesQuotation.items))
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
    requested_team_ids = [assignment.partner_id for assignment in req.sales_team]
    if len(requested_team_ids) != len(set(requested_team_ids)):
        raise HTTPException(status_code=422, detail="A sales partner can only appear once on a sales team.")
    if req.sales_team and sum((row.contribution_pct for row in req.sales_team), Decimal("0")) != Decimal("100"):
        raise HTTPException(status_code=422, detail="Sales team contribution percentages must total exactly 100%.")
    sales_partners = (await db.scalars(select(SalesPartner).where(
        SalesPartner.tenant_id == tenant_id,
        SalesPartner.sales_partner_id.in_(requested_team_ids) if requested_team_ids else SalesPartner.sales_partner_id.is_(None),
        SalesPartner.is_active.is_(True),
    ))).all()
    sales_partners_by_id = {partner.sales_partner_id: partner for partner in sales_partners}
    if len(sales_partners_by_id) != len(requested_team_ids):
        raise HTTPException(status_code=422, detail="Every sales partner must be active and belong to this workspace.")
    contact = None
    if req.customer_contact_id:
        contact = await db.scalar(select(Contact).where(
            Contact.tenant_id == tenant_id, Contact.contact_id == req.customer_contact_id,
            Contact.is_active.is_(True),
        ))
        if contact is None:
            raise HTTPException(status_code=422, detail="Customer contact must be active and belong to this workspace.")
    addresses: dict[uuid.UUID, Address] = {}
    selected_addresses = {value for value in (req.billing_address_id, req.shipping_address_id) if value}
    if selected_addresses:
        addresses = {row.address_id: row for row in (await db.scalars(select(Address).where(
            Address.tenant_id == tenant_id, Address.address_id.in_(selected_addresses),
        ))).all()}
        if set(addresses) != selected_addresses:
            raise HTTPException(status_code=422, detail="Billing and shipping addresses must belong to this workspace.")
    if req.terms_template_id:
        terms_template = await db.scalar(select(TermsAndConditionsTemplate).where(
            TermsAndConditionsTemplate.tenant_id == tenant_id,
            TermsAndConditionsTemplate.terms_template_id == req.terms_template_id,
            TermsAndConditionsTemplate.is_active.is_(True),
            TermsAndConditionsTemplate.applicable_to.in_(("SELLING", "BOTH")),
        ))
        if terms_template is None:
            raise HTTPException(status_code=422, detail="Terms template must be an active selling template in this workspace.")
    else:
        terms_template = None
    if req.price_list_id:
        price_list = await db.scalar(select(PriceList.price_list_id).where(
            PriceList.tenant_id == tenant_id, PriceList.price_list_id == req.price_list_id,
            PriceList.selling.is_(True), PriceList.is_active.is_(True),
        ))
        if price_list is None:
            raise HTTPException(status_code=422, detail="Price list must be active and enabled for selling.")
    if req.shipping_rule_id:
        shipping_rule = await db.scalar(select(ShippingRule.shipping_rule_id).where(
            ShippingRule.tenant_id == tenant_id, ShippingRule.shipping_rule_id == req.shipping_rule_id,
            ShippingRule.is_active.is_(True),
        ))
        if shipping_rule is None:
            raise HTTPException(status_code=422, detail="Shipping rule must be active and belong to this workspace.")
    order_num = req.order_number or f"SO-{quote.quotation_number.replace('QT-', '')}"
    source_quote_lines: list[SalesQuotationItem | None]
    if quote.items:
        quote_items_by_id = {line.quotation_item_id: line for line in quote.items}
        requested_quote_line_ids = [line.quotation_item_id for line in req.items]
        if any(requested_quote_line_ids):
            if any(line_id is None for line_id in requested_quote_line_ids) or len(set(requested_quote_line_ids)) != len(req.items):
                raise HTTPException(status_code=422, detail="Each converted line must identify a unique source quotation line.")
            if set(requested_quote_line_ids) != set(quote_items_by_id):
                raise HTTPException(status_code=409, detail="Converted lines must include every source quotation line exactly once.")
            source_quote_lines = [quote_items_by_id[line_id] for line_id in requested_quote_line_ids]
        else:
            # Compatibility for older clients only works where each item appears once.
            quote_items_by_item = {line.item_id: line for line in quote.items}
            if len(quote_items_by_item) != len(quote.items) or len({line.item_id for line in req.items}) != len(req.items):
                raise HTTPException(status_code=422, detail="This quotation has repeated items; refresh the client to convert its individual source lines.")
            source_quote_lines = [quote_items_by_item.get(line.item_id) for line in req.items]
    else:
        source_quote_lines = [None] * len(req.items)
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
    if len(items) != len(set(item_ids)):
        raise HTTPException(status_code=422, detail="Every order line must reference an active tenant-owned sales item.")
    total_amt = sum((line.quantity * line.unit_price for line in req.items), Decimal("0.0000"))
    if total_amt <= 0 or total_amt >= Decimal("100000000000000"):
        raise HTTPException(status_code=422, detail="Order total is outside the supported monetary range.")
    expected_line_total = quote.subtotal if quote.items else quote.total_amount
    if total_amt != expected_line_total:
        raise HTTPException(status_code=409, detail="Order line amount must match the accepted quotation subtotal.")
    if quote.items and any(
        source is None or source.item_id != line.item_id
        or source.quantity != line.quantity or source.unit_price != line.unit_price
        for line, source in zip(req.items, source_quote_lines, strict=True)
    ):
        raise HTTPException(status_code=409, detail="Sales order lines must match the accepted quotation line snapshots.")
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
                SalesOrder.status.in__(("PENDING_CONFIRMATION", "CONFIRMED", "BACKORDERED", "PARTIALLY_DELIVERED")),
            )
        )
    ).scalar_one()
    credit_exposure = Decimal(str(open_invoice_total)) + Decimal(str(other_open_order_total)) + quote.total_amount
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
        required_by_item: dict[uuid.UUID, Decimal] = {}
        for line, source_quote_line in zip(req.items, source_quote_lines, strict=True):
            required_stock = (
                source_quote_line.stock_quantity
                if source_quote_line and source_quote_line.stock_quantity > 0
                else line.quantity * source_quote_line.conversion_factor
                if source_quote_line
                else line.quantity
            )
            required_by_item[line.item_id] = required_by_item.get(line.item_id, Decimal("0")) + required_stock
        for required_item_id, required_stock in sorted(required_by_item.items(), key=lambda pair: str(pair[0])):
            stock = stock_by_item.get(required_item_id)
            if stock is None or stock.is_quarantined or stock.current_qty - stock.reserved_qty < required_stock:
                break
            candidate.append((stock, required_stock))
        if len(candidate) == len(required_by_item):
            chosen_warehouse = warehouse
            reservation_rows = candidate
            break
    if chosen_warehouse is None:
        raise HTTPException(status_code=409, detail="No active warehouse can reserve every quote line from available, unquarantined stock.")

    order = SalesOrder(
        tenant_id=tenant_id,
        order_number=order_num,
        customer_id=quote.customer_id,
        source_quotation_id=quote.quotation_id,
        order_date=date.today(),
        delivery_date=req.delivery_date or quote.valid_until,
        subtotal=quote.subtotal,
        tax_amount=quote.tax_amount,
        total_amount=quote.total_amount,
        status="CONFIRMED",
        fulfillment_warehouse_id=chosen_warehouse.warehouse_id,
        customer_contact_id=req.customer_contact_id,
        customer_contact_snapshot=({key: getattr(contact, key) for key in ("full_name", "email", "phone", "designation")} if contact else None),
        billing_address_id=req.billing_address_id,
        billing_address_snapshot=({key: getattr(addresses[req.billing_address_id], key) for key in ("address_title", "address_type", "address_line1", "address_line2", "city", "state", "postal_code", "country")} if req.billing_address_id else None),
        shipping_address_id=req.shipping_address_id,
        shipping_address_snapshot=({key: getattr(addresses[req.shipping_address_id], key) for key in ("address_title", "address_type", "address_line1", "address_line2", "city", "state", "postal_code", "country")} if req.shipping_address_id else None),
        terms_template_id=req.terms_template_id,
        terms_text=req.terms_text if req.terms_text is not None else (terms_template.terms if terms_template else None),
        price_list_id=quote.price_list_id or req.price_list_id,
        shipping_rule_id=quote.shipping_rule_id or req.shipping_rule_id,
        payment_terms=req.payment_terms or f"Net {customer.payment_terms_days} days",
        exchange_rate=req.exchange_rate,
        discount_amount=quote.discount_amount,
        taxes_and_charges=quote.tax_amount,
        shipping_charge=quote.shipping_charge,
        sales_tax_template_id=quote.sales_tax_template_id,
        tax_snapshot=quote.tax_snapshot,
        calculation_hash=quote.calculation_hash,
        submitted_at=datetime.now(UTC),
    )
    db.add(order)
    await db.flush()
    for assignment in req.sales_team:
        partner = sales_partners_by_id[assignment.partner_id]
        db.add(SalesTeam(
            tenant_id=tenant_id,
            document_type="SALES_ORDER",
            document_id=order.order_id,
            sales_partner_id=partner.sales_partner_id,
            contribution_pct=assignment.contribution_pct,
            commission_rate=assignment.commission_rate if assignment.commission_rate is not None else partner.commission_rate,
        ))
    for it, source_quote_line in zip(req.items, source_quote_lines, strict=True):
        so_item = SalesOrderItem(
            tenant_id=tenant_id,
            order_id=order.order_id,
            item_id=it.item_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            line_total=source_quote_line.line_total if source_quote_line else it.quantity * it.unit_price,
            stock_quantity=source_quote_line.stock_quantity if source_quote_line else it.quantity,
            uom_id=source_quote_line.uom_id if source_quote_line else None,
            conversion_factor=source_quote_line.conversion_factor if source_quote_line else Decimal("1"),
            price_list_id=source_quote_line.price_list_id if source_quote_line else quote.price_list_id,
            item_price_id=source_quote_line.item_price_id if source_quote_line else None,
            price_list_rate=source_quote_line.price_list_rate if source_quote_line else it.unit_price,
            discount_amount=source_quote_line.discount_amount if source_quote_line else Decimal("0"),
            pricing_rule_id=source_quote_line.pricing_rule_id if source_quote_line else None,
            promotion_id=source_quote_line.promotion_id if source_quote_line else None,
            is_free=source_quote_line.is_free if source_quote_line else False,
            source_quotation_item_id=(source_quote_line.quotation_item_id if source_quote_line else None),
        )
        db.add(so_item)
    for stock, quantity in reservation_rows:
        stock.reserved_qty += quantity
        stock.available_qty = stock.current_qty - stock.reserved_qty
    quote.status = "ACCEPTED"
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id,
        operation="SALES_ORDER_SUBMITTED",
        idempotency_key=str(order.order_id),
        status="COMPLETED",
        input_snapshot={"quotation_id": str(quote.quotation_id)},
        result_snapshot={"order_number": order.order_number, "status": order.status},
        completed_at=datetime.now(UTC),
    ))
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
    if order.amended_from_order_id:
        original = await db.scalar(select(SalesOrder).where(
            SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == order.amended_from_order_id,
        ).with_for_update())
        if original is None or original.status != "CANCELLED":
            raise HTTPException(status_code=409, detail="Cancel the original sales order before confirming its amendment.")

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
    stock_requirements: dict[uuid.UUID, Decimal] = {}
    for line in lines:
        required_stock = line.stock_quantity or (line.quantity * line.conversion_factor)
        stock_requirements[line.item_id] = stock_requirements.get(line.item_id, Decimal("0")) + required_stock
    reservations: list[tuple[StockLevel, Decimal]] | None = None
    chosen_warehouse: Warehouse | None = None
    for warehouse in warehouses:
        stocks = (
            await db.execute(
                select(StockLevel)
                .where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.warehouse_id == warehouse.warehouse_id,
                    StockLevel.item_id.in_(stock_requirements),
                )
                .order_by(StockLevel.item_id)
                .with_for_update()
            )
        ).scalars().all()
        stock_by_item = {stock.item_id: stock for stock in stocks}
        candidate: list[tuple[StockLevel, Decimal]] = []
        for item_id, required_stock in stock_requirements.items():
            stock = stock_by_item.get(item_id)
            if stock is None or stock.is_quarantined:
                break
            available = stock.current_qty - stock.reserved_qty
            if available < required_stock:
                break
            candidate.append((stock, required_stock))
        if len(candidate) == len(stock_requirements):
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
    order.submitted_at = datetime.now(UTC)
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id,
        operation="SALES_ORDER_SUBMITTED",
        idempotency_key=str(order.order_id),
        status="COMPLETED",
        input_snapshot={"order_id": str(order.order_id)},
        result_snapshot={"order_number": order.order_number, "status": order.status},
        completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return {
        "order_id": str(order.order_id),
        "status": order.status,
        "warehouse_id": str(chosen_warehouse.warehouse_id),
        "stock_reserved": True,
    }


@router.post("/orders/{order_id}/cancel", summary="Cancel an unfulfilled sales order")
async def cancel_sales_order(order_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    order = (await db.execute(select(SalesOrder).options(selectinload(SalesOrder.items)).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == order_id,
    ).with_for_update())).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found.")
    if order.status == "CANCELLED":
        return order
    if order.status not in {"PENDING_CONFIRMATION", "CONFIRMED", "BACKORDERED"}:
        raise HTTPException(status_code=409, detail="Orders with delivered quantities cannot be cancelled; record a return or credit note.")
    downstream = await db.scalar(select(DeliveryNote.delivery_note_id).where(
        DeliveryNote.tenant_id == tenant_id, DeliveryNote.order_id == order.order_id,
    ).limit(1).with_for_update())
    if downstream or any(line.delivered_quantity > 0 or line.invoiced_quantity > 0 for line in order.items):
        raise HTTPException(status_code=409, detail="Orders with delivery or invoice activity cannot be cancelled directly.")
    if order.status == "CONFIRMED" and order.fulfillment_warehouse_id:
        quantities: dict[uuid.UUID, Decimal] = {}
        for line in order.items:
            remaining_entered = line.quantity - line.delivered_quantity
            remaining_stock = remaining_entered * line.conversion_factor
            quantities[line.item_id] = quantities.get(line.item_id, Decimal("0")) + (
                line.stock_quantity - line.delivered_quantity * line.conversion_factor
                if line.stock_quantity > 0
                else remaining_stock
            )
        stocks = (await db.scalars(select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.warehouse_id == order.fulfillment_warehouse_id,
            StockLevel.item_id.in_(quantities),
        ).order_by(StockLevel.item_id).with_for_update())).all()
        stock_by_item = {row.item_id: row for row in stocks}
        for item_id, quantity in quantities.items():
            stock = stock_by_item.get(item_id)
            if stock is None or stock.reserved_qty < quantity:
                raise HTTPException(status_code=409, detail="Reserved inventory changed; reconcile stock before cancelling the order.")
        for item_id, quantity in quantities.items():
            stock = stock_by_item[item_id]
            stock.reserved_qty -= quantity
            stock.available_qty = stock.current_qty - stock.reserved_qty
    order.status = "CANCELLED"
    order.cancelled_at = datetime.now(UTC)
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="SALES_ORDER_CANCELLED", idempotency_key=str(order.order_id),
        status="COMPLETED", input_snapshot={"order_id": str(order.order_id)},
        result_snapshot={"order_number": order.order_number, "status": order.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return order


@router.post("/orders/{order_id}/amend", status_code=status.HTTP_201_CREATED, summary="Create a draft amendment of a sales order")
async def amend_sales_order(
    order_id: uuid.UUID,
    req: AmendSalesOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reviewer: User = controller_review_dep,
):
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    original = (await db.execute(select(SalesOrder).options(selectinload(SalesOrder.items)).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == order_id,
    ).with_for_update())).scalar_one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="Sales order not found.")
    if original.status not in {"PENDING_CONFIRMATION", "CONFIRMED"}:
        raise HTTPException(status_code=409, detail="Only an unfulfilled sales order can be amended.")
    duplicate = await db.scalar(select(SalesOrder.order_id).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.order_number == req.order_number,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="Sales-order number already exists in this workspace.")
    downstream = await db.scalar(select(DeliveryNote.delivery_note_id).where(
        DeliveryNote.tenant_id == tenant_id, DeliveryNote.order_id == original.order_id,
    ).limit(1))
    if downstream or any(line.delivered_quantity or line.invoiced_quantity for line in original.items):
        raise HTTPException(status_code=409, detail="An order with delivery or invoice activity cannot be amended.")
    revision = SalesOrder(
        tenant_id=tenant_id, order_number=req.order_number, customer_id=original.customer_id,
        order_date=date.today(), delivery_date=original.delivery_date, total_amount=original.total_amount,
        status="PENDING_CONFIRMATION", amended_from_order_id=original.order_id,
        source_quotation_id=original.source_quotation_id, customer_contact_id=original.customer_contact_id,
        customer_contact_snapshot=original.customer_contact_snapshot,
        billing_address_id=original.billing_address_id, billing_address_snapshot=original.billing_address_snapshot,
        shipping_address_id=original.shipping_address_id, shipping_address_snapshot=original.shipping_address_snapshot,
        terms_template_id=original.terms_template_id, terms_text=original.terms_text,
        price_list_id=original.price_list_id, shipping_rule_id=original.shipping_rule_id,
        payment_terms=original.payment_terms, exchange_rate=original.exchange_rate,
        subtotal=original.subtotal, tax_amount=original.tax_amount,
        discount_amount=original.discount_amount, taxes_and_charges=original.taxes_and_charges,
    )
    db.add(revision)
    await db.flush()
    for line in original.items:
        db.add(SalesOrderItem(
            tenant_id=tenant_id, order_id=revision.order_id, item_id=line.item_id,
            source_quotation_item_id=line.source_quotation_item_id, quantity=line.quantity,
            unit_price=line.unit_price, line_total=line.line_total, uom_id=line.uom_id,
            conversion_factor=line.conversion_factor, stock_quantity=line.stock_quantity,
            price_list_id=line.price_list_id, item_price_id=line.item_price_id,
            price_list_rate=line.price_list_rate,
        ))
    db.add(DocumentAuditBatch(
        tenant_id=tenant_id, operation="SALES_ORDER_AMENDMENT_CREATED", idempotency_key=str(revision.order_id),
        status="COMPLETED", input_snapshot={"original_order_id": str(original.order_id)},
        result_snapshot={"order_number": revision.order_number, "status": revision.status}, completed_at=datetime.now(UTC),
    ))
    await db.flush()
    return revision


@router.get("/orders/{order_id}/timeline", summary="Sales order source links and audit timeline")
async def sales_order_timeline(order_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    order = (await db.execute(select(SalesOrder).options(selectinload(SalesOrder.items)).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.order_id == order_id,
    ))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found.")
    deliveries = (await db.scalars(select(DeliveryNote).where(
        DeliveryNote.tenant_id == tenant_id, DeliveryNote.order_id == order_id,
    ).order_by(DeliveryNote.delivery_date))).all()
    invoices = (await db.scalars(select(SalesInvoice).where(
        SalesInvoice.tenant_id == tenant_id, SalesInvoice.order_id == order_id,
    ).order_by(SalesInvoice.invoice_date))).all()
    events = (await db.scalars(select(DocumentAuditBatch).where(
        DocumentAuditBatch.tenant_id == tenant_id,
        DocumentAuditBatch.idempotency_key == str(order_id),
        DocumentAuditBatch.operation.like("SALES_ORDER_%"),
    ).order_by(DocumentAuditBatch.created_at))).all()
    return {"document": order,
        "source_links": {"source_quotation_id": str(order.source_quotation_id) if order.source_quotation_id else None,
            "amended_from_order_id": str(order.amended_from_order_id) if order.amended_from_order_id else None,
            "lines": [{"order_item_id": str(line.order_item_id), "source_quotation_item_id": str(line.source_quotation_item_id) if line.source_quotation_item_id else None,
                "delivered_quantity": line.delivered_quantity, "invoiced_quantity": line.invoiced_quantity,
                "remaining_to_deliver": line.quantity - line.delivered_quantity,
                "remaining_to_invoice": line.delivered_quantity - line.invoiced_quantity} for line in order.items]},
        "delivery_notes": deliveries, "sales_invoices": invoices, "audit_events": events}


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

    if order.status not in {"CONFIRMED", "BACKORDERED", "PARTIALLY_DELIVERED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sales order must be confirmed and have undelivered quantities before fulfillment.",
        )

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

    order_items_by_id = {line.order_item_id: line for line in order.items}
    if req.items is None:
        fulfill_quantities = {
            line.order_item_id: line.quantity - line.delivered_quantity
            for line in order.items
            if line.quantity > line.delivered_quantity
        }
    else:
        fulfill_quantities = {}
        for requested in req.items:
            if requested.order_item_id in fulfill_quantities:
                raise HTTPException(status_code=422, detail="A sales order line may appear only once per delivery note.")
            line = order_items_by_id.get(requested.order_item_id)
            if line is None:
                raise HTTPException(status_code=422, detail="Every fulfillment line must belong to this sales order.")
            remaining = line.quantity - line.delivered_quantity
            if requested.quantity > remaining:
                raise HTTPException(status_code=409, detail="Fulfillment quantity exceeds the undelivered order quantity.")
            fulfill_quantities[requested.order_item_id] = requested.quantity
    if not fulfill_quantities:
        raise HTTPException(status_code=409, detail="No undelivered quantities remain on this sales order.")
    order_quantities: dict[uuid.UUID, Decimal] = {}
    for order_item_id, quantity in fulfill_quantities.items():
        order_line = order_items_by_id[order_item_id]
        item_id = order_line.item_id
        stock_quantity = quantity * order_line.conversion_factor
        order_quantities[item_id] = order_quantities.get(item_id, Decimal("0.0000")) + stock_quantity
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

    delivery_count = await db.scalar(
        select(func.count(DeliveryNote.delivery_note_id)).where(
            DeliveryNote.tenant_id == tenant_id, DeliveryNote.order_id == order.order_id
        )
    )
    dn_number = f"DN-{order.order_number}" if not delivery_count else f"DN-{order.order_number}-{delivery_count + 1}"
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

    for order_item_id, quantity in fulfill_quantities.items():
        itm = order_items_by_id[order_item_id]
        dn_item = DeliveryNoteItem(
            tenant_id=tenant_id,
            delivery_note_id=dn.delivery_note_id,
            order_item_id=itm.order_item_id,
            item_id=itm.item_id,
            warehouse_id=wh_id,
            quantity=quantity,
        )
        db.add(dn_item)

        itm.delivered_quantity += quantity

        stk = stock_by_item[itm.item_id]
        stock_quantity = quantity * itm.conversion_factor
        stk.current_qty -= stock_quantity
        stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - stock_quantity)
        stk.available_qty = stk.current_qty - stk.reserved_qty
        rate = stk.valuation_rate
        qty_after = stk.current_qty

        sle = StockLedgerEntry(
            tenant_id=tenant_id,
            posting_datetime=datetime.now(UTC),
            item_id=itm.item_id,
            warehouse_id=wh_id,
            actual_qty=-stock_quantity,
            qty_after_transaction=qty_after,
            valuation_rate=rate,
            stock_value_difference=-stock_quantity * rate,
            source_document_type="DELIVERY_NOTE",
            source_document_id=dn.delivery_note_id,
        )
        db.add(sle)

    order.status = "DELIVERED" if all(line.delivered_quantity >= line.quantity for line in order.items) else "PARTIALLY_DELIVERED"
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

    if order is None or order.status not in {"PARTIALLY_DELIVERED", "DELIVERED"}:
        raise HTTPException(status_code=409, detail="A partially or fully delivered sales order is required before invoicing.")
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
    order_items_by_id = {item.order_item_id: item for item in order.items}
    validated_lines: list[tuple[DeliveryNoteItem, SalesOrderItem, Decimal, Decimal]] = []
    total_amt = Decimal("0.0000")
    for dn_item in dn.items:
        order_item = order_items_by_id.get(dn_item.order_item_id)
        if order_item is None or order_item.item_id != dn_item.item_id:
            raise HTTPException(status_code=409, detail="Delivery note lines do not match the tenant sales order.")
        if order_item.invoiced_quantity + dn_item.quantity > order_item.delivered_quantity:
            raise HTTPException(status_code=409, detail="Delivery note includes quantities already invoiced or not yet delivered.")
        line_discount = (
            order_item.discount_amount * dn_item.quantity / order_item.quantity
            if order_item.quantity else Decimal("0.0000")
        ).quantize(Decimal("0.0001"))
        line_total = dn_item.quantity * order_item.unit_price - line_discount
        total_amt += line_total
        validated_lines.append((dn_item, order_item, line_discount, line_total))
    if not validated_lines:
        raise HTTPException(status_code=409, detail="An empty delivery note cannot be invoiced.")
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
    source_team = (await db.scalars(select(SalesTeam).where(
        SalesTeam.tenant_id == tenant_id,
        SalesTeam.document_id == order.order_id,
        SalesTeam.document_type.in_(("SALES_ORDER", "Sales Order")),
    ))).all()
    partner_ids = {assignment.sales_partner_id for assignment in source_team}
    partners = (await db.scalars(select(SalesPartner).where(
        SalesPartner.tenant_id == tenant_id,
        SalesPartner.sales_partner_id.in_(partner_ids) if partner_ids else SalesPartner.sales_partner_id.is_(None),
    ))).all()
    try:
        invoice_team = invoice_sales_team_snapshot(
            source_team, {partner.sales_partner_id: partner for partner in partners}, tenant_id, invoice.invoice_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(invoice)
    db.add_all(invoice_team)
    await db.flush()

    for itm, order_item, line_discount, line_total in validated_lines:
        sinv_item = SalesInvoiceItem(
            tenant_id=tenant_id,
            invoice_id=invoice.invoice_id,
            item_id=itm.item_id,
            quantity=itm.quantity,
            unit_price=order_item.unit_price,
            line_total=line_total,
            discount_amount=line_discount,
            order_item_id=order_item.order_item_id,
            delivery_note_item_id=itm.dn_item_id,
        )
        db.add(sinv_item)
        order_item.invoiced_quantity += itm.quantity

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


@router.get("/delivery-notes", summary="List tenant delivery notes and invoice status")
async def list_delivery_notes(tenant_id: TenantIdDep, db: DbSessionDep):
    notes = (await db.scalars(
        select(DeliveryNote)
        .options(selectinload(DeliveryNote.items), selectinload(DeliveryNote.customer))
        .where(DeliveryNote.tenant_id == tenant_id)
        .order_by(DeliveryNote.delivery_date.desc(), DeliveryNote.delivery_note_number.desc())
        .limit(500)
    )).all()
    invoice_ids = [note.delivery_note_id for note in notes]
    invoices = (await db.scalars(select(SalesInvoice).where(
        SalesInvoice.tenant_id == tenant_id,
        SalesInvoice.delivery_note_id.in_(invoice_ids) if invoice_ids else SalesInvoice.delivery_note_id.is_(None),
    ))).all()
    invoice_by_note = {invoice.delivery_note_id: invoice for invoice in invoices if invoice.delivery_note_id}
    return [{
        "delivery_note_id": note.delivery_note_id,
        "delivery_note_number": note.delivery_note_number,
        "order_id": note.order_id,
        "customer_id": note.customer_id,
        "customer_name": note.customer.customer_name if note.customer else "",
        "delivery_date": note.delivery_date,
        "status": note.status,
        "item_count": len(note.items),
        "invoice_id": invoice_by_note[note.delivery_note_id].invoice_id if note.delivery_note_id in invoice_by_note else None,
        "invoice_number": invoice_by_note[note.delivery_note_id].invoice_number if note.delivery_note_id in invoice_by_note else None,
    } for note in notes]
