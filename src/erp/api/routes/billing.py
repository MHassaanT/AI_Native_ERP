"""Phase 1 Accounts, POS, and Billing API Endpoints with Complete ERPNext Parity."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.billing import (
    AdvancePaymentAllocation,
    Budget,
    CreditNote,
    CreditNoteItem,
    DebitNote,
    DebitNoteItem,
    DunningNotice,
    DunningType,
    PaymentSchedule,
    PaymentTermsTemplate,
    PaymentTermsTemplateDetail,
    POSClosingEntry,
    POSInvoice,
    POSInvoiceItem,
    POSInvoiceMergeLog,
    POSInvoicePayment,
    POSOpeningEntry,
    POSParkedCart,
    POSProfile,
    SalesTaxesAndChargesTemplate,
    SalesTaxesAndChargesTemplateDetail,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
    TaxWithholdingCategory,
)
from erp.db.models.sales import Customer, SalesInvoice
from erp.workflows.billing.budget_service import BudgetService
from erp.workflows.billing.dunning_service import DunningService
from erp.workflows.billing.pos_service import POSService
from erp.workflows.billing.returns_service import ReturnsService
from erp.workflows.billing.subscription_service import SubscriptionService
from erp.workflows.billing.tax_and_terms_service import TaxAndTermsService

router = APIRouter(prefix="/billing", tags=["Accounts, POS & Invoicing"])

pos_service = POSService()
subscription_service = SubscriptionService()
dunning_service = DunningService()
budget_service = BudgetService()
returns_service = ReturnsService()
tax_terms_service = TaxAndTermsService()


# ==========================================
# Pydantic Schemas
# ==========================================


class CreatePOSProfileRequest(BaseModel):
    profile_name: str = Field(..., min_length=2, max_length=128)
    warehouse_id: uuid.UUID
    cost_center: str = "Main - CC"
    currency: str = "USD"
    income_account: str = "4000-SALES-REVENUE"
    expense_account: str = "5000-COGS"
    allow_discount_change: bool = True
    allow_rate_change: bool = False


class OpenPOSShiftRequest(BaseModel):
    profile_id: uuid.UUID
    user_id: uuid.UUID
    opening_float_cash: Decimal = Decimal("100.0000")


class ClosePOSShiftRequest(BaseModel):
    opening_id: uuid.UUID
    actual_counted_cash: Decimal


class POSItemLine(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal = Decimal("0.00")


class POSPaymentLine(BaseModel):
    payment_method: str = "CASH"  # CASH, CARD, VOUCHER, LOYALTY
    amount: Decimal
    reference_no: str | None = None


class CreatePOSInvoiceRequest(BaseModel):
    opening_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    items: list[POSItemLine]
    payment_method: str = "CASH"  # CASH, CARD, SPLIT
    paid_amount: Decimal | None = None
    payment_details: dict | None = None
    payments: list[POSPaymentLine] | None = None
    is_return: bool = False
    return_against: str | None = None


class ParkPOSCartRequest(BaseModel):
    profile_id: uuid.UUID
    user_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    cart_data: Any
    hold_note: str | None = None


class CreateSubscriptionPlanRequest(BaseModel):
    plan_name: str = Field(..., min_length=2, max_length=128)
    billing_interval: str = "MONTHLY"  # MONTHLY, QUARTERLY, ANNUAL
    currency: str = "USD"
    cost: Decimal


class SubscriptionItemLine(BaseModel):
    plan_id: uuid.UUID
    quantity: Decimal = Decimal("1.0000")
    unit_cost: Decimal


class SubscribeCustomerRequest(BaseModel):
    customer_id: uuid.UUID
    plan_id: uuid.UUID
    start_date: date | None = None
    trial_days: int = 0
    items: list[SubscriptionItemLine] | None = None


class PauseSubscriptionRequest(BaseModel):
    resume_at: date | None = None


class ProratePreviewRequest(BaseModel):
    base_cost: Decimal
    days_active: int
    total_days_in_period: int = 30


class PaymentTermDetailSchema(BaseModel):
    description: str
    invoice_portion: Decimal  # e.g. 30.00
    due_date_based_on: str = "Day(s) after invoice date"
    credit_days: int = 0


class CreatePaymentTermsTemplateRequest(BaseModel):
    template_name: str = Field(..., min_length=2, max_length=128)
    terms: list[PaymentTermDetailSchema]
    allocate_payment_based_on_payment_terms: bool = True


class ApplyPaymentTermsRequest(BaseModel):
    template_id: uuid.UUID


class TaxTemplateDetailSchema(BaseModel):
    charge_type: str = "On Net Total"  # Actual, On Net Total, On Previous Row Amount
    row_id: int | None = None
    account_head: str
    description: str
    rate: Decimal = Decimal("0.0000")


class CreateTaxTemplateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=128)
    tax_category: str = "Standard"
    is_default: bool = False
    taxes: list[TaxTemplateDetailSchema] = []


class CalculateTaxesRequest(BaseModel):
    net_total: Decimal
    taxes: list[TaxTemplateDetailSchema]


class AllocateAdvanceRequest(BaseModel):
    customer_id: uuid.UUID
    allocated_amount: Decimal
    reference_note: str | None = None


class CreateDunningTypeRequest(BaseModel):
    dunning_type_name: str = Field(..., min_length=2, max_length=64)
    overdue_days: int = 15
    fee_amount: Decimal = Decimal("25.0000")
    interest_rate_pct: Decimal = Decimal("2.50")
    message_body: str = "Your invoice is overdue. Please settle immediately."


class CreateBudgetRequest(BaseModel):
    budget_name: str = Field(..., min_length=2, max_length=128)
    fiscal_year: int
    cost_center: str
    account_code: str
    budget_amount: Decimal
    action_on_exceed: str = "WARN"  # WARN, STOP, IGNORE


class BudgetCheckRequest(BaseModel):
    fiscal_year: int
    cost_center: str
    account_code: str
    proposed_expense: Decimal


class ReturnItemLine(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal


class CreateCreditNoteRequest(BaseModel):
    customer_id: uuid.UUID
    reason: str
    items: list[ReturnItemLine]
    invoice_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None


class CreateDebitNoteRequest(BaseModel):
    supplier_id: uuid.UUID
    reason: str
    items: list[ReturnItemLine]
    supplier_invoice_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None


class CreateTaxWithholdingCategoryRequest(BaseModel):
    category_name: str
    section_code: str
    rate_pct: Decimal = Decimal("10.00")
    single_threshold: Decimal = Decimal("30000.0000")
    cumulative_threshold: Decimal = Decimal("100000.0000")


# ==========================================
# 1. Point of Sale (POS) Endpoints
# ==========================================


@router.post("/pos/profiles", status_code=status.HTTP_201_CREATED)
async def create_pos_profile(
    payload: CreatePOSProfileRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    profile = POSProfile(
        tenant_id=tenant_id,
        profile_name=payload.profile_name,
        warehouse_id=payload.warehouse_id,
        cost_center=payload.cost_center,
        currency=payload.currency,
        income_account=payload.income_account,
        expense_account=payload.expense_account,
        allow_discount_change=payload.allow_discount_change,
        allow_rate_change=payload.allow_rate_change,
    )
    session.add(profile)
    await session.commit()
    return {"message": "POS profile created successfully", "profile_id": str(profile.profile_id)}


@router.get("/pos/profiles")
async def list_pos_profiles(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(POSProfile).where(POSProfile.tenant_id == tenant_id)
    res = await session.execute(stmt)
    profiles = res.scalars().all()
    return [
        {
            "profile_id": str(p.profile_id),
            "profile_name": p.profile_name,
            "warehouse_id": str(p.warehouse_id),
            "cost_center": p.cost_center,
            "currency": p.currency,
            "is_active": p.is_active,
        }
        for p in profiles
    ]


@router.post("/pos/shifts/open")
async def open_pos_shift(
    payload: OpenPOSShiftRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    shift = await pos_service.open_shift(
        session=session,
        tenant_id=tenant_id,
        profile_id=payload.profile_id,
        user_id=payload.user_id,
        opening_float_cash=payload.opening_float_cash,
    )
    await session.commit()
    return {
        "message": "POS shift opened",
        "opening_id": str(shift.opening_id),
        "status": shift.status,
        "opening_float_cash": float(shift.opening_float_cash),
        "period_start_date": shift.period_start_date.isoformat(),
    }


@router.get("/pos/shifts/current")
async def get_current_pos_shift(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    user_id: uuid.UUID = Query(...),
):
    stmt = select(POSOpeningEntry).where(
        POSOpeningEntry.tenant_id == tenant_id,
        POSOpeningEntry.user_id == user_id,
        POSOpeningEntry.status == "OPEN",
    )
    res = await session.execute(stmt)
    shift = res.scalars().first()
    if not shift:
        return {"has_open_shift": False}

    return {
        "has_open_shift": True,
        "opening_id": str(shift.opening_id),
        "profile_id": str(shift.profile_id),
        "opening_float_cash": float(shift.opening_float_cash),
        "period_start_date": shift.period_start_date.isoformat(),
    }


@router.post("/pos/shifts/close")
async def close_pos_shift(
    payload: ClosePOSShiftRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    closing = await pos_service.close_shift(
        session=session,
        tenant_id=tenant_id,
        opening_id=payload.opening_id,
        actual_counted_cash=payload.actual_counted_cash,
    )
    await session.commit()
    return {
        "message": "POS shift closed and reconciled",
        "closing_id": str(closing.closing_id),
        "total_sales": float(closing.total_sales_amount),
        "expected_cash": float(closing.expected_cash),
        "actual_counted_cash": float(closing.actual_counted_cash),
        "cash_variance": float(closing.cash_variance),
        "status": closing.status,
    }


@router.post("/pos/invoices", status_code=status.HTTP_201_CREATED)
async def create_pos_invoice(
    payload: CreatePOSInvoiceRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    items_dicts = [it.model_dump() for it in payload.items]
    payments_dicts = [p.model_dump() for p in payload.payments] if payload.payments else None

    invoice, gl_tx_id = await pos_service.process_pos_sale(
        session=session,
        tenant_id=tenant_id,
        opening_id=payload.opening_id,
        customer_id=payload.customer_id,
        items=items_dicts,
        payment_method=payload.payment_method,
        paid_amount=payload.paid_amount,
        payment_details=payload.payment_details,
        payments=payments_dicts,
        is_return=payload.is_return,
        return_against=payload.return_against,
    )
    await session.commit()

    # Load complete invoice details with relationships
    stmt = (
        select(POSInvoice)
        .options(
            selectinload(POSInvoice.items).joinedload(POSInvoiceItem.item),
            selectinload(POSInvoice.payments),
            joinedload(POSInvoice.customer),
            joinedload(POSInvoice.opening_entry).joinedload(POSOpeningEntry.pos_profile),
        )
        .where(POSInvoice.pos_invoice_id == invoice.pos_invoice_id)
    )
    res = await session.execute(stmt)
    full_invoice = res.scalars().first() or invoice

    return {
        "message": "POS invoice processed successfully",
        "pos_invoice_id": str(full_invoice.pos_invoice_id),
        "pos_invoice_number": full_invoice.pos_invoice_number,
        "posting_date": full_invoice.posting_date.isoformat(),
        "posting_time": full_invoice.posting_time.isoformat() if full_invoice.posting_time else None,
        "customer_id": str(full_invoice.customer_id),
        "customer_name": full_invoice.customer.customer_name if full_invoice.customer else "Walk-In Retail Customer",
        "customer_code": full_invoice.customer.customer_code if full_invoice.customer else "CUST-WALK-IN",
        "subtotal": float(full_invoice.subtotal),
        "tax_amount": float(full_invoice.tax_amount),
        "discount_amount": float(full_invoice.discount_amount),
        "grand_total": float(full_invoice.grand_total),
        "paid_amount": float(full_invoice.paid_amount),
        "change_amount": float(full_invoice.change_amount),
        "payment_method": full_invoice.payment_method,
        "is_return": full_invoice.is_return,
        "return_against": full_invoice.return_against,
        "status": full_invoice.status,
        "profile_name": (
            full_invoice.opening_entry.pos_profile.profile_name
            if full_invoice.opening_entry and full_invoice.opening_entry.pos_profile
            else "Main Retail Store"
        ),
        "items": [
            {
                "pos_item_id": str(it.pos_item_id),
                "item_id": str(it.item_id),
                "item_code": it.item.item_code if it.item else "ITEM",
                "item_name": it.item.item_name if it.item else "Product Item",
                "quantity": float(it.quantity),
                "unit_price": float(it.unit_price),
                "discount_pct": float(it.discount_pct),
                "amount": float(it.line_total),
            }
            for it in full_invoice.items
        ],
        "payments": [
            {
                "payment_method": p.payment_method,
                "amount": float(p.amount),
                "reference_no": p.reference_no,
            }
            for p in full_invoice.payments
        ],
        "gl_transaction_id": str(gl_tx_id) if gl_tx_id else None,
    }


@router.get("/pos/invoices/{invoice_id}")
async def get_pos_invoice(
    invoice_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(POSInvoice)
        .options(
            selectinload(POSInvoice.items).joinedload(POSInvoiceItem.item),
            selectinload(POSInvoice.payments),
            joinedload(POSInvoice.customer),
            joinedload(POSInvoice.opening_entry).joinedload(POSOpeningEntry.pos_profile),
        )
        .where(
            POSInvoice.pos_invoice_id == invoice_id,
            POSInvoice.tenant_id == tenant_id,
        )
    )
    res = await session.execute(stmt)
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="POS Invoice not found")

    return {
        "pos_invoice_id": str(inv.pos_invoice_id),
        "pos_invoice_number": inv.pos_invoice_number,
        "posting_date": inv.posting_date.isoformat(),
        "posting_time": inv.posting_time.isoformat() if inv.posting_time else None,
        "customer_id": str(inv.customer_id),
        "customer_name": inv.customer.customer_name if inv.customer else "Walk-In Retail Customer",
        "customer_code": inv.customer.customer_code if inv.customer else "CUST-WALK-IN",
        "subtotal": float(inv.subtotal),
        "tax_amount": float(inv.tax_amount),
        "discount_amount": float(inv.discount_amount),
        "grand_total": float(inv.grand_total),
        "paid_amount": float(inv.paid_amount),
        "change_amount": float(inv.change_amount),
        "payment_method": inv.payment_method,
        "is_return": inv.is_return,
        "return_against": inv.return_against,
        "status": inv.status,
        "profile_name": (
            inv.opening_entry.pos_profile.profile_name
            if inv.opening_entry and inv.opening_entry.pos_profile
            else "Main Retail Store"
        ),
        "items": [
            {
                "pos_item_id": str(it.pos_item_id),
                "item_id": str(it.item_id),
                "item_code": it.item.item_code if it.item else "ITEM",
                "item_name": it.item.item_name if it.item else "Product Item",
                "quantity": float(it.quantity),
                "unit_price": float(it.unit_price),
                "discount_pct": float(it.discount_pct),
                "amount": float(it.line_total),
            }
            for it in inv.items
        ],
        "payments": [
            {
                "payment_method": p.payment_method,
                "amount": float(p.amount),
                "reference_no": p.reference_no,
            }
            for p in inv.payments
        ],
    }


@router.get("/pos/invoices/lookup/{invoice_ref}")
async def lookup_pos_invoice(
    invoice_ref: str,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Looks up a POS invoice by either pos_invoice_id (UUID) or human-readable receipt number (e.g. POS-20260930-XXXX)."""
    clean_ref = invoice_ref.strip()
    query_cond = None
    try:
        inv_uuid = uuid.UUID(clean_ref)
        query_cond = (POSInvoice.pos_invoice_id == inv_uuid)
    except ValueError:
        query_cond = (func.lower(POSInvoice.pos_invoice_number) == clean_ref.lower())

    stmt = (
        select(POSInvoice)
        .options(
            selectinload(POSInvoice.items).joinedload(POSInvoiceItem.item),
            selectinload(POSInvoice.payments),
            joinedload(POSInvoice.customer),
            joinedload(POSInvoice.opening_entry).joinedload(POSOpeningEntry.pos_profile),
        )
        .where(
            query_cond,
            POSInvoice.tenant_id == tenant_id,
        )
    )
    res = await session.execute(stmt)
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(
            status_code=404,
            detail=f"POS Invoice or Receipt '{clean_ref}' not found."
        )

    return {
        "pos_invoice_id": str(inv.pos_invoice_id),
        "pos_invoice_number": inv.pos_invoice_number,
        "posting_date": inv.posting_date.isoformat(),
        "posting_time": inv.posting_time.isoformat() if inv.posting_time else None,
        "customer_id": str(inv.customer_id) if inv.customer_id else None,
        "customer_name": inv.customer.customer_name if inv.customer else "Walk-In Retail Customer",
        "customer_code": inv.customer.customer_code if inv.customer else "CUST-WALK-IN",
        "subtotal": float(inv.subtotal),
        "tax_amount": float(inv.tax_amount),
        "discount_amount": float(inv.discount_amount),
        "grand_total": float(inv.grand_total),
        "paid_amount": float(inv.paid_amount),
        "change_amount": float(inv.change_amount),
        "payment_method": inv.payment_method,
        "is_return": inv.is_return,
        "return_against": inv.return_against,
        "status": inv.status,
        "profile_name": (
            inv.opening_entry.pos_profile.profile_name
            if inv.opening_entry and inv.opening_entry.pos_profile
            else "Main Retail Store"
        ),
        "items": [
            {
                "pos_item_id": str(it.pos_item_id),
                "item_id": str(it.item_id),
                "item_code": it.item.item_code if it.item else "ITEM",
                "item_name": it.item.item_name if it.item else "Product Item",
                "quantity": float(it.quantity),
                "unit_price": float(it.unit_price),
                "discount_pct": float(it.discount_pct),
                "amount": float(it.line_total),
            }
            for it in inv.items
        ],
        "payments": [
            {
                "payment_method": p.payment_method,
                "amount": float(p.amount),
                "reference_no": p.reference_no,
            }
            for p in inv.payments
        ],
    }


@router.get("/pos/invoices")
async def list_pos_invoices(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    opening_id: uuid.UUID | None = Query(None),
):
    stmt = select(POSInvoice).where(POSInvoice.tenant_id == tenant_id)
    if opening_id:
        stmt = stmt.where(POSInvoice.opening_id == opening_id)
    stmt = stmt.order_by(POSInvoice.created_at.desc())
    res = await session.execute(stmt)
    invoices = res.scalars().all()
    return [
        {
            "pos_invoice_id": str(inv.pos_invoice_id),
            "pos_invoice_number": inv.pos_invoice_number,
            "posting_date": inv.posting_date.isoformat(),
            "grand_total": float(inv.grand_total),
            "payment_method": inv.payment_method,
            "is_return": inv.is_return,
            "status": inv.status,
        }
        for inv in invoices
    ]


@router.post("/pos/park-cart")
async def park_pos_cart(
    payload: ParkPOSCartRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    cart = await pos_service.park_cart(
        session=session,
        tenant_id=tenant_id,
        profile_id=payload.profile_id,
        user_id=payload.user_id,
        cart_data=payload.cart_data,
        customer_id=payload.customer_id,
        hold_note=payload.hold_note,
    )
    await session.commit()
    return {"message": "Cart held successfully", "parked_id": str(cart.parked_id)}


@router.get("/pos/parked-carts")
async def list_parked_pos_carts(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    profile_id: uuid.UUID | None = Query(None),
):
    carts = await pos_service.list_parked_carts(session=session, tenant_id=tenant_id, profile_id=profile_id)
    return [
        {
            "parked_id": str(c.parked_id),
            "profile_id": str(c.profile_id),
            "customer_name": c.customer.customer_name if c.customer else "Walk-In Customer",
            "hold_note": c.hold_note,
            "cart_data": c.cart_data,
            "created_at": c.created_at.isoformat(),
        }
        for c in carts
    ]


@router.post("/pos/parked-carts/{parked_id}/restore")
async def restore_parked_pos_cart(
    parked_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    cart = await pos_service.restore_parked_cart(session=session, tenant_id=tenant_id, parked_id=parked_id)
    await session.commit()
    return {"message": "Cart restored", "cart_data": cart.cart_data}


@router.delete("/pos/parked-carts/{parked_id}")
async def delete_parked_pos_cart(
    parked_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    await pos_service.delete_parked_cart(session=session, tenant_id=tenant_id, parked_id=parked_id)
    await session.commit()
    return {"message": "Parked cart discarded"}


@router.post("/pos/shifts/{closing_id}/consolidate")
async def consolidate_shift_invoices(
    closing_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    try:
        merge_log = await pos_service.consolidate_shift_invoices(
            session=session,
            tenant_id=tenant_id,
            closing_id=closing_id,
        )
        await session.commit()
        return {
            "message": f"Successfully consolidated {merge_log.total_invoices_merged} POS invoices",
            "merge_log_id": str(merge_log.merge_log_id),
            "total_invoices_merged": merge_log.total_invoices_merged,
            "total_grand_total": float(merge_log.total_amount),
            "consolidated_invoice_id": str(merge_log.consolidated_invoice_id) if merge_log.consolidated_invoice_id else None,
            "consolidated_credit_note_id": str(merge_log.consolidated_credit_note_id) if merge_log.consolidated_credit_note_id else None,
        }
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# 2. Subscriptions Endpoints
# ==========================================


@router.post("/subscriptions/plans", status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    payload: CreateSubscriptionPlanRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    plan = await subscription_service.create_plan(
        session=session,
        tenant_id=tenant_id,
        plan_name=payload.plan_name,
        billing_interval=payload.billing_interval,
        cost=payload.cost,
        currency=payload.currency,
    )
    await session.commit()
    return {"message": "Subscription plan created", "plan_id": str(plan.plan_id)}


@router.get("/subscriptions/plans")
async def list_subscription_plans(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.tenant_id == tenant_id)
    res = await session.execute(stmt)
    plans = res.scalars().all()
    return [
        {
            "plan_id": str(p.plan_id),
            "plan_name": p.plan_name,
            "billing_interval": p.billing_interval,
            "cost": float(p.cost),
            "currency": p.currency,
            "is_active": p.is_active,
        }
        for p in plans
    ]


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def subscribe_customer(
    payload: SubscribeCustomerRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    items_dicts = [it.model_dump() for it in payload.items] if payload.items else None
    sub = await subscription_service.subscribe_customer(
        session=session,
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        plan_id=payload.plan_id,
        start_date=payload.start_date,
        trial_days=payload.trial_days,
        items=items_dicts,
    )
    await session.commit()
    return {
        "message": "Subscription established",
        "subscription_id": str(sub.subscription_id),
        "status": sub.status,
        "next_billing_date": sub.next_billing_date.isoformat(),
        "trial_period_end": sub.trial_period_end.isoformat() if sub.trial_period_end else None,
    }


@router.get("/subscriptions")
async def list_subscriptions(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(Subscription)
        .options(
            selectinload(Subscription.plan),
            selectinload(Subscription.customer),
            selectinload(Subscription.items).selectinload(SubscriptionItem.plan),
        )
        .where(Subscription.tenant_id == tenant_id)
    )
    res = await session.execute(stmt)
    subs = res.scalars().all()
    return [
        {
            "subscription_id": str(s.subscription_id),
            "customer_id": str(s.customer_id),
            "customer_name": s.customer.customer_name if s.customer else "Unknown",
            "plan_id": str(s.plan_id),
            "plan_name": s.plan.plan_name if s.plan else "Unknown",
            "cost": float(sum((it.quantity * it.unit_cost for it in s.items), Decimal("0.0000"))) if s.items else (float(s.plan.cost) if s.plan else 0.0),
            "status": s.status,
            "start_date": s.start_date.isoformat(),
            "next_billing_date": s.next_billing_date.isoformat(),
            "trial_period_end": s.trial_period_end.isoformat() if s.trial_period_end else None,
            "paused_at": s.paused_at.isoformat() if s.paused_at else None,
            "resume_at": s.resume_at.isoformat() if s.resume_at else None,
            "items": [
                {
                    "sub_item_id": str(it.sub_item_id),
                    "plan_id": str(it.plan_id),
                    "plan_name": it.plan.plan_name if it.plan else "Plan Item",
                    "quantity": float(it.quantity),
                    "unit_cost": float(it.unit_cost),
                }
                for it in s.items
            ],
        }
        for s in subs
    ]


@router.post("/subscriptions/{subscription_id}/pause")
async def pause_subscription(
    subscription_id: uuid.UUID,
    payload: PauseSubscriptionRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    sub = await subscription_service.pause_subscription(
        session=session,
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        resume_at=payload.resume_at,
    )
    await session.commit()
    return {"message": "Subscription paused", "subscription_id": str(sub.subscription_id), "status": sub.status}


@router.post("/subscriptions/{subscription_id}/resume")
async def resume_subscription(
    subscription_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    sub = await subscription_service.resume_subscription(
        session=session,
        tenant_id=tenant_id,
        subscription_id=subscription_id,
    )
    await session.commit()
    return {"message": "Subscription resumed", "subscription_id": str(sub.subscription_id), "status": sub.status}


@router.post("/subscriptions/prorate-preview")
async def preview_proration(payload: ProratePreviewRequest):
    prorated = subscription_service.calculate_proration(
        base_cost=payload.base_cost,
        days_active=payload.days_active,
        total_days_in_period=payload.total_days_in_period,
    )
    return {
        "base_cost": float(payload.base_cost),
        "days_active": payload.days_active,
        "total_days_in_period": payload.total_days_in_period,
        "prorated_charge": float(prorated),
    }


@router.post("/subscriptions/process-billing")
async def trigger_subscription_billing(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    as_of_date: date | None = None,
):
    invoices = await subscription_service.process_recurring_billing(
        session=session,
        tenant_id=tenant_id,
        as_of_date=as_of_date,
    )
    await session.commit()
    return {
        "message": f"Processed {len(invoices)} recurring subscription renewals",
        "generated_invoices": invoices,
    }


# ==========================================
# 3. Payment Terms & Schedules
# ==========================================


@router.post("/payment-terms/templates", status_code=status.HTTP_201_CREATED)
async def create_payment_terms_template(
    payload: CreatePaymentTermsTemplateRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    terms_dicts = [t.model_dump() for t in payload.terms]
    tmpl = await tax_terms_service.create_payment_terms_template(
        session=session,
        tenant_id=tenant_id,
        template_name=payload.template_name,
        terms=terms_dicts,
        allocate_payment_based_on_payment_terms=payload.allocate_payment_based_on_payment_terms,
    )
    await session.commit()
    return {"message": "Payment terms template created", "template_id": str(tmpl.template_id)}


@router.get("/payment-terms/templates")
async def list_payment_terms_templates(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(PaymentTermsTemplate)
        .options(selectinload(PaymentTermsTemplate.terms))
        .where(PaymentTermsTemplate.tenant_id == tenant_id)
    )
    res = await session.execute(stmt)
    templates = res.scalars().all()
    return [
        {
            "template_id": str(t.template_id),
            "template_name": t.template_name,
            "allocate_payment_based_on_payment_terms": t.allocate_payment_based_on_payment_terms,
            "terms": [
                {
                    "detail_id": str(d.detail_id),
                    "description": d.description,
                    "invoice_portion": float(d.invoice_portion),
                    "due_date_based_on": d.due_date_based_on,
                    "credit_days": d.credit_days,
                }
                for d in t.terms
            ],
        }
        for t in templates
    ]


@router.get("/invoices")
async def list_sales_invoices(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(SalesInvoice)
        .options(selectinload(SalesInvoice.customer))
        .where(SalesInvoice.tenant_id == tenant_id)
        .order_by(SalesInvoice.created_at.desc())
    )
    res = await session.execute(stmt)
    invoices = res.scalars().all()
    return [
        {
            "invoice_id": str(inv.invoice_id),
            "invoice_number": inv.invoice_number,
            "customer_id": str(inv.customer_id) if inv.customer_id else None,
            "customer_name": inv.customer.customer_name if inv.customer else "Walk-In Customer",
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "currency": inv.currency,
            "subtotal": float(inv.subtotal),
            "tax_amount": float(inv.tax_amount),
            "total_amount": float(inv.total_amount),
            "status": inv.status,
            "outstanding_amount": float(getattr(inv, "outstanding_amount", None) if getattr(inv, "outstanding_amount", None) is not None else inv.total_amount),
        }
        for inv in invoices
    ]


@router.post("/invoices/{invoice_id}/apply-payment-terms")
async def apply_payment_terms_to_invoice(
    invoice_id: uuid.UUID,
    payload: ApplyPaymentTermsRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    schedules = await tax_terms_service.generate_payment_schedule_for_invoice(
        session=session,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        template_id=payload.template_id,
    )
    await session.commit()
    return {
        "message": f"Generated {len(schedules)} installment payment schedules",
        "schedules": [
            {
                "schedule_id": str(s.schedule_id),
                "payment_term": s.payment_term,
                "due_date": s.due_date.isoformat(),
                "portion_pct": float(s.portion_pct),
                "portion_amount": float(s.portion_amount),
                "outstanding_amount": float(s.outstanding_amount),
                "status": s.status,
            }
            for s in schedules
        ],
    }


@router.get("/invoices/{invoice_id}/payment-schedule")
async def get_invoice_payment_schedule(
    invoice_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(PaymentSchedule).where(
        PaymentSchedule.invoice_id == invoice_id,
        PaymentSchedule.tenant_id == tenant_id,
    ).order_by(PaymentSchedule.due_date.asc())
    res = await session.execute(stmt)
    schedules = res.scalars().all()
    return [
        {
            "schedule_id": str(s.schedule_id),
            "payment_term": s.payment_term,
            "due_date": s.due_date.isoformat(),
            "portion_pct": float(s.portion_pct),
            "portion_amount": float(s.portion_amount),
            "paid_amount": float(s.paid_amount),
            "outstanding_amount": float(s.outstanding_amount),
            "status": s.status,
        }
        for s in schedules
    ]


# ==========================================
# 4. Multi-Tier Sales Taxes & Charges Templates
# ==========================================


@router.post("/tax-templates", status_code=status.HTTP_201_CREATED)
async def create_tax_template(
    payload: CreateTaxTemplateRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    taxes_dicts = [t.model_dump() for t in payload.taxes]
    tmpl = await tax_terms_service.create_tax_template(
        session=session,
        tenant_id=tenant_id,
        title=payload.title,
        tax_category=payload.tax_category,
        is_default=payload.is_default,
        taxes=taxes_dicts,
    )
    await session.commit()
    return {"message": "Tax template created", "template_id": str(tmpl.template_id)}


@router.get("/tax-templates")
async def list_tax_templates(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(SalesTaxesAndChargesTemplate)
        .options(selectinload(SalesTaxesAndChargesTemplate.taxes))
        .where(SalesTaxesAndChargesTemplate.tenant_id == tenant_id)
    )
    res = await session.execute(stmt)
    templates = res.scalars().all()
    return [
        {
            "template_id": str(t.template_id),
            "title": t.title,
            "tax_category": t.tax_category,
            "is_default": t.is_default,
            "taxes": [
                {
                    "detail_id": str(d.detail_id),
                    "charge_type": d.charge_type,
                    "row_id": d.row_id,
                    "account_head": d.account_head,
                    "description": d.description,
                    "rate": float(d.rate),
                }
                for d in t.taxes
            ],
        }
        for t in templates
    ]


@router.post("/tax-templates/calculate")
async def calculate_cascading_taxes(payload: CalculateTaxesRequest):
    taxes_dicts = [t.model_dump() for t in payload.taxes]
    calc = tax_terms_service.calculate_taxes_and_charges(
        net_total=payload.net_total,
        tax_details=taxes_dicts,
    )
    return calc


# ==========================================
# 5. Customer Advance Payment Allocation
# ==========================================


@router.post("/invoices/{invoice_id}/reconcile-advance")
async def reconcile_advance_payment(
    invoice_id: uuid.UUID,
    payload: AllocateAdvanceRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    allocation = await tax_terms_service.allocate_advance_payment(
        session=session,
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        invoice_id=invoice_id,
        allocated_amount=payload.allocated_amount,
        reference_note=payload.reference_note,
    )
    await session.commit()
    return {
        "message": f"Successfully allocated ${float(allocation.allocated_amount)} advance towards invoice",
        "allocation_id": str(allocation.allocation_id),
        "allocated_amount": float(allocation.allocated_amount),
    }


@router.get("/invoices/{invoice_id}/advance-allocations")
async def list_invoice_advance_allocations(
    invoice_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(AdvancePaymentAllocation)
        .where(
            AdvancePaymentAllocation.invoice_id == invoice_id,
            AdvancePaymentAllocation.tenant_id == tenant_id,
        )
        .order_by(AdvancePaymentAllocation.posting_date.desc())
    )
    res = await session.execute(stmt)
    allocs = res.scalars().all()
    return [
        {
            "allocation_id": str(a.allocation_id),
            "allocated_amount": float(a.allocated_amount),
            "reference_note": a.reference_note,
            "posting_date": a.posting_date.isoformat(),
        }
        for a in allocs
    ]


# ==========================================
# 6. Dunning Endpoints
# ==========================================


@router.post("/dunning/types", status_code=status.HTTP_201_CREATED)
async def create_dunning_type(
    payload: CreateDunningTypeRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    dtype = await dunning_service.create_dunning_type(
        session=session,
        tenant_id=tenant_id,
        dunning_type_name=payload.dunning_type_name,
        overdue_days=payload.overdue_days,
        fee_amount=payload.fee_amount,
        interest_rate_pct=payload.interest_rate_pct,
        message_body=payload.message_body,
    )
    await session.commit()
    return {"message": "Dunning level created", "dunning_type_id": str(dtype.dunning_type_id)}


@router.get("/dunning/types")
async def list_dunning_types(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(DunningType).where(DunningType.tenant_id == tenant_id).order_by(DunningType.overdue_days.asc())
    res = await session.execute(stmt)
    types = res.scalars().all()
    return [
        {
            "dunning_type_id": str(t.dunning_type_id),
            "dunning_type_name": t.dunning_type_name,
            "overdue_days": t.overdue_days,
            "fee_amount": float(t.fee_amount),
            "interest_rate_pct": float(t.interest_rate_pct),
        }
        for t in types
    ]


@router.post("/dunning/evaluate-overdue")
async def evaluate_overdue_and_issue_dunning(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    as_of_date: date | None = None,
):
    notices = await dunning_service.evaluate_overdue_invoices(
        session=session,
        tenant_id=tenant_id,
        as_of_date=as_of_date,
    )
    await session.commit()
    return {
        "message": f"Issued {len(notices)} overdue dunning notices",
        "dunning_notices": notices,
    }


@router.get("/dunning/notices")
async def list_dunning_notices(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(DunningNotice)
        .options(selectinload(DunningNotice.customer), selectinload(DunningNotice.dunning_type))
        .where(DunningNotice.tenant_id == tenant_id)
        .order_by(DunningNotice.posting_date.desc())
    )
    res = await session.execute(stmt)
    notices = res.scalars().all()
    return [
        {
            "notice_id": str(n.notice_id),
            "notice_number": n.notice_number,
            "customer_name": n.customer.customer_name if n.customer else "Unknown",
            "overdue_days": n.overdue_days,
            "outstanding_amount": float(n.outstanding_amount),
            "fee_amount": float(n.fee_amount),
            "interest_amount": float(n.interest_amount),
            "total_dunning_amount": float(n.total_dunning_amount),
            "status": n.status,
            "posting_date": n.posting_date.isoformat(),
        }
        for n in notices
    ]


# ==========================================
# 7. Budgeting Endpoints
# ==========================================


@router.post("/budgets", status_code=status.HTTP_201_CREATED)
async def create_budget(
    payload: CreateBudgetRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    budget = await budget_service.create_budget(
        session=session,
        tenant_id=tenant_id,
        budget_name=payload.budget_name,
        fiscal_year=payload.fiscal_year,
        cost_center=payload.cost_center,
        account_code=payload.account_code,
        budget_amount=payload.budget_amount,
        action_on_exceed=payload.action_on_exceed,
    )
    await session.commit()
    return {"message": "Budget registered", "budget_id": str(budget.budget_id)}


@router.get("/budgets")
async def list_budgets(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(Budget).where(Budget.tenant_id == tenant_id)
    res = await session.execute(stmt)
    budgets = res.scalars().all()
    return [
        {
            "budget_id": str(b.budget_id),
            "budget_name": b.budget_name,
            "fiscal_year": b.fiscal_year,
            "cost_center": b.cost_center,
            "account_code": b.account_code,
            "budget_amount": float(b.budget_amount),
            "action_on_exceed": b.action_on_exceed,
        }
        for b in budgets
    ]


@router.post("/budgets/check")
async def check_budget_compliance(
    payload: BudgetCheckRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    return await budget_service.evaluate_budget_compliance(
        session=session,
        tenant_id=tenant_id,
        fiscal_year=payload.fiscal_year,
        cost_center=payload.cost_center,
        account_code=payload.account_code,
        proposed_expense=payload.proposed_expense,
    )


# ==========================================
# 8. Credit Notes & Debit Notes Endpoints
# ==========================================


@router.post("/credit-notes", status_code=status.HTTP_201_CREATED)
async def create_credit_note(
    payload: CreateCreditNoteRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    items_dicts = [it.model_dump() for it in payload.items]
    credit_note = await returns_service.issue_credit_note(
        session=session,
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        reason=payload.reason,
        items=items_dicts,
        invoice_id=payload.invoice_id,
        warehouse_id=payload.warehouse_id,
    )
    await session.commit()
    return {
        "message": "Credit Note issued successfully",
        "credit_note_id": str(credit_note.credit_note_id),
        "credit_note_number": credit_note.credit_note_number,
        "total_amount": float(credit_note.total_amount),
        "status": credit_note.status,
    }


@router.get("/credit-notes")
async def list_credit_notes(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(CreditNote)
        .options(selectinload(CreditNote.customer))
        .where(CreditNote.tenant_id == tenant_id)
        .order_by(CreditNote.posting_date.desc())
    )
    res = await session.execute(stmt)
    cns = res.scalars().all()
    return [
        {
            "credit_note_id": str(c.credit_note_id),
            "credit_note_number": c.credit_note_number,
            "customer_name": c.customer.customer_name if c.customer else "Unknown",
            "reason": c.reason,
            "subtotal": float(c.subtotal),
            "tax_amount": float(c.tax_amount),
            "total_amount": float(c.total_amount),
            "status": c.status,
            "posting_date": c.posting_date.isoformat(),
        }
        for c in cns
    ]


@router.post("/debit-notes", status_code=status.HTTP_201_CREATED)
async def create_debit_note(
    payload: CreateDebitNoteRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    items_dicts = [it.model_dump() for it in payload.items]
    debit_note = await returns_service.issue_debit_note(
        session=session,
        tenant_id=tenant_id,
        supplier_id=payload.supplier_id,
        reason=payload.reason,
        items=items_dicts,
        supplier_invoice_id=payload.supplier_invoice_id,
        warehouse_id=payload.warehouse_id,
    )
    await session.commit()
    return {
        "message": "Debit Note issued successfully",
        "debit_note_id": str(debit_note.debit_note_id),
        "debit_note_number": debit_note.debit_note_number,
        "total_amount": float(debit_note.total_amount),
        "status": debit_note.status,
    }


@router.get("/debit-notes")
async def list_debit_notes(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = (
        select(DebitNote)
        .options(selectinload(DebitNote.supplier))
        .where(DebitNote.tenant_id == tenant_id)
        .order_by(DebitNote.posting_date.desc())
    )
    res = await session.execute(stmt)
    dns = res.scalars().all()
    return [
        {
            "debit_note_id": str(d.debit_note_id),
            "debit_note_number": d.debit_note_number,
            "supplier_name": d.supplier.supplier_name if d.supplier else "Unknown",
            "reason": d.reason,
            "subtotal": float(d.subtotal),
            "tax_amount": float(d.tax_amount),
            "total_amount": float(d.total_amount),
            "status": d.status,
            "posting_date": d.posting_date.isoformat(),
        }
        for d in dns
    ]


# ==========================================
# 9. Tax Withholding (TDS) Endpoints
# ==========================================


@router.post("/tax-withholding/categories", status_code=status.HTTP_201_CREATED)
async def create_tax_withholding_category(
    payload: CreateTaxWithholdingCategoryRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    category = TaxWithholdingCategory(
        tenant_id=tenant_id,
        category_name=payload.category_name,
        section_code=payload.section_code,
        rate_pct=payload.rate_pct,
        single_threshold=payload.single_threshold,
        cumulative_threshold=payload.cumulative_threshold,
    )
    session.add(category)
    await session.commit()
    return {"message": "Tax withholding category created", "category_id": str(category.category_id)}


@router.get("/tax-withholding/categories")
async def list_tax_withholding_categories(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    stmt = select(TaxWithholdingCategory).where(TaxWithholdingCategory.tenant_id == tenant_id)
    res = await session.execute(stmt)
    categories = res.scalars().all()
    return [
        {
            "category_id": str(c.category_id),
            "category_name": c.category_name,
            "section_code": c.section_code,
            "rate_pct": float(c.rate_pct),
            "single_threshold": float(c.single_threshold),
            "cumulative_threshold": float(c.cumulative_threshold),
        }
        for c in categories
    ]
