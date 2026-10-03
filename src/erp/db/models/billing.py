"""Phase 1 Accounts & Invoicing Expansion Models.

Covers:
- Credit Notes & Debit Notes (Sales/Purchase returns)
- Point of Sale (POS): Profiles, Opening Shifts, Closing Shifts, POS Invoices
- Subscriptions: Plans, Customer Subscriptions, Recurring Invoices
- Dunning: Levels, Overdue Notices, Late Payment Interest & Fees
- Budgeting: Annual/Monthly Budgets, Cost Center Allocations, Warning/Stopping Thresholds
- Tax Withholding / TDS: Withholding Categories, Rate Brackets, Withheld Entries
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)

from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


# ==========================================
# 1. Credit Notes & Debit Notes (Returns)
# ==========================================


class CreditNote(Base, TenantMixin, TimestampMixin):
    """Credit Note recording sales return and Accounts Receivable reduction."""

    __tablename__ = "credit_notes"

    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    credit_note_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="POSTED")  # DRAFT, POSTED, CANCELLED

    customer = relationship("Customer")
    sales_invoice = relationship("SalesInvoice")
    items: Mapped[list["CreditNoteItem"]] = relationship(back_populates="credit_note", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_cn_tenant_number", "tenant_id", "credit_note_number", unique=True),
    )


class CreditNoteItem(Base, TenantMixin, TimestampMixin):
    """Line item on Credit Note."""

    __tablename__ = "credit_note_items"

    cn_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_notes.credit_note_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    credit_note = relationship("CreditNote", back_populates="items")
    item = relationship("Item")


class DebitNote(Base, TenantMixin, TimestampMixin):
    """Debit Note recording purchase return and Accounts Payable reduction."""

    __tablename__ = "debit_notes"

    debit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    debit_note_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_invoices.invoice_id"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="POSTED")  # DRAFT, POSTED, CANCELLED

    supplier = relationship("Supplier")
    supplier_invoice = relationship("SupplierInvoice")
    items: Mapped[list["DebitNoteItem"]] = relationship(back_populates="debit_note", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_dn_debit_tenant_number", "tenant_id", "debit_note_number", unique=True),
    )


class DebitNoteItem(Base, TenantMixin, TimestampMixin):
    """Line item on Debit Note."""

    __tablename__ = "debit_note_items"

    dn_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    debit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debit_notes.debit_note_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    debit_note = relationship("DebitNote", back_populates="items")
    item = relationship("Item")


# ==========================================
# 2. Point of Sale (POS) System
# ==========================================


class POSProfile(Base, TenantMixin, TimestampMixin):
    """POS Terminal Profile configuring defaults and allowed cashiers."""

    __tablename__ = "pos_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    cost_center: Mapped[str] = mapped_column(String(64), nullable=False, default="Main - CC")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    income_account: Mapped[str] = mapped_column(String(32), nullable=False, default="4000-SALES-REVENUE")
    expense_account: Mapped[str] = mapped_column(String(32), nullable=False, default="5000-COGS")
    allow_discount_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_rate_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    warehouse = relationship("Warehouse")

    __table_args__ = (
        Index("idx_pos_profile_name", "tenant_id", "profile_name", unique=True),
    )


class POSOpeningEntry(Base, TenantMixin, TimestampMixin):
    """POS Cashier Shift Opening Record."""

    __tablename__ = "pos_opening_entries"

    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_profiles.profile_id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    period_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    opening_float_cash: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")  # OPEN, CLOSED

    pos_profile = relationship("POSProfile")
    user = relationship("User")

    __table_args__ = (
        Index("idx_pos_opening_status", "tenant_id", "user_id", "status"),
    )


class POSClosingEntry(Base, TenantMixin, TimestampMixin):
    """POS Cashier Shift Closing and Reconciliation Record."""

    __tablename__ = "pos_closing_entries"

    closing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_opening_entries.opening_id"), nullable=False
    )
    period_end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    total_sales_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_collected_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_collected_card: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_collected_other: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    actual_counted_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    cash_variance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUBMITTED")  # DRAFT, SUBMITTED

    opening_entry = relationship("POSOpeningEntry")


class POSInvoice(Base, TenantMixin, TimestampMixin):
    """High-speed retail transaction invoice."""

    __tablename__ = "pos_invoices"

    pos_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pos_invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_opening_entries.opening_id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    posting_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, default="CASH")  # CASH, CARD, SPLIT
    payment_details: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )  # {"cash": 50, "card": 50}
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PAID")  # PAID, RETURNED, CANCELLED
    is_return: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    return_against: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consolidated_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    customer = relationship("Customer")
    opening_entry = relationship("POSOpeningEntry")
    items: Mapped[list["POSInvoiceItem"]] = relationship(back_populates="pos_invoice", cascade="all, delete-orphan")
    payments: Mapped[list["POSInvoicePayment"]] = relationship(back_populates="pos_invoice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_pos_inv_tenant_num", "tenant_id", "pos_invoice_number", unique=True),
    )


class POSInvoicePayment(Base, TenantMixin, TimestampMixin):
    """Split payment line for POS Invoices."""

    __tablename__ = "pos_invoice_payments"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pos_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_invoices.pos_invoice_id"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, default="CASH")  # CASH, CARD, VOUCHER, LOYALTY
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)

    pos_invoice = relationship("POSInvoice", back_populates="payments")


class POSParkedCart(Base, TenantMixin, TimestampMixin):
    """Parked / Held POS order cart."""

    __tablename__ = "pos_parked_carts"

    parked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_profiles.profile_id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True
    )
    hold_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cart_data: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PARKED")  # PARKED, RESTORED, CANCELLED

    pos_profile = relationship("POSProfile")
    user = relationship("User")
    customer = relationship("Customer")


class POSInvoiceMergeLog(Base, TenantMixin, TimestampMixin):
    """Log record of POS Invoices consolidated into master Sales Invoice and Credit Note."""

    __tablename__ = "pos_invoice_merge_logs"

    merge_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    closing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_closing_entries.closing_id"), nullable=True
    )
    opening_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_opening_entries.opening_id"), nullable=True
    )
    consolidated_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=True
    )
    consolidated_credit_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_notes.credit_note_id"), nullable=True
    )
    total_invoices_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    closing_entry = relationship("POSClosingEntry")
    opening_entry = relationship("POSOpeningEntry")
    consolidated_invoice = relationship("SalesInvoice")
    consolidated_credit_note = relationship("CreditNote")


class POSInvoiceItem(Base, TenantMixin, TimestampMixin):
    """Line item in a POS Invoice."""

    __tablename__ = "pos_invoice_items"

    pos_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pos_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_invoices.pos_invoice_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    pos_invoice = relationship("POSInvoice", back_populates="items")
    item = relationship("Item")


# ==========================================
# 3. Subscriptions & Recurring Billing
# ==========================================


class SubscriptionPlan(Base, TenantMixin, TimestampMixin):
    """SaaS or Recurring Service Plan."""

    __tablename__ = "subscription_plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(32), nullable=False, default="MONTHLY")  # MONTHLY, QUARTERLY, ANNUAL
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_sub_plan_name", "tenant_id", "plan_name", unique=True),
    )


class Subscription(Base, TenantMixin, TimestampMixin):
    """Customer active subscription contract."""

    __tablename__ = "subscriptions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.plan_id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    next_billing_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")  # TRIALING, ACTIVE, GRACE_PERIOD, PAST_DUE, PAUSED, CANCELLED, COMPLETED
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trial_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    trial_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resume_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    customer = relationship("Customer")
    plan = relationship("SubscriptionPlan")
    items: Mapped[list["SubscriptionItem"]] = relationship(back_populates="subscription", cascade="all, delete-orphan")


class SubscriptionItem(Base, TenantMixin, TimestampMixin):
    """Multi-plan item line on a Subscription."""

    __tablename__ = "subscription_items"

    sub_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.subscription_id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.plan_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("1.0000"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    subscription = relationship("Subscription", back_populates="items")
    plan = relationship("SubscriptionPlan")


# ==========================================
# 4. Dunning & Overdue Payment Management
# ==========================================


class DunningType(Base, TenantMixin, TimestampMixin):
    """Dunning level configuring overdue thresholds, interest, and fees."""

    __tablename__ = "dunning_types"

    dunning_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dunning_type_name: Mapped[str] = mapped_column(String(64), nullable=False)  # Level 1, Level 2, Final Notice
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("25.0000"))
    interest_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("2.50"))
    message_body: Mapped[str] = mapped_column(Text, nullable=False, default="Your invoice is overdue. Please settle immediately.")

    __table_args__ = (
        Index("idx_dunning_type_name", "tenant_id", "dunning_type_name", unique=True),
    )


class DunningNotice(Base, TenantMixin, TimestampMixin):
    """Formal Dunning Notice issued to customer for overdue invoice."""

    __tablename__ = "dunning_notices"

    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    notice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    dunning_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dunning_types.dunning_type_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    interest_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_dunning_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ISSUED")  # DRAFT, ISSUED, RESOLVED

    customer = relationship("Customer")
    sales_invoice = relationship("SalesInvoice")
    dunning_type = relationship("DunningType")

    __table_args__ = (
        Index("idx_dunning_tenant_number", "tenant_id", "notice_number", unique=True),
    )


# ==========================================
# 5. Budgeting & Financial Control
# ==========================================


class Budget(Base, TenantMixin, TimestampMixin):
    """Financial Budget allocated to a Cost Center or Project."""

    __tablename__ = "budgets"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    budget_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_center: Mapped[str] = mapped_column(String(64), nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    action_on_exceed: Mapped[str] = mapped_column(String(16), nullable=False, default="WARN")  # WARN, STOP, IGNORE
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_budget_lookup", "tenant_id", "fiscal_year", "cost_center", "account_code"),
    )


# ==========================================
# 6. Tax Withholding / TDS
# ==========================================


class TaxWithholdingCategory(Base, TenantMixin, TimestampMixin):
    """Tax Deducted at Source (TDS) / Withholding Tax category."""

    __tablename__ = "tax_withholding_categories"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_name: Mapped[str] = mapped_column(String(128), nullable=False)  # Professional Fees 194J, Contractor 194C
    section_code: Mapped[str] = mapped_column(String(32), nullable=False)
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10.00"))
    single_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("30000.0000"))
    cumulative_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("100000.0000"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_tds_cat_name", "tenant_id", "category_name", unique=True),
    )


# ==========================================
# 7. Payment Terms Templates & Payment Schedules
# ==========================================


class PaymentTermsTemplate(Base, TenantMixin, TimestampMixin):
    """Payment Terms Template defining milestone payment schedules."""

    __tablename__ = "payment_terms_templates"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    allocate_payment_based_on_payment_terms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    terms: Mapped[list["PaymentTermsTemplateDetail"]] = relationship(back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ptt_name", "tenant_id", "template_name", unique=True),
    )


class PaymentTermsTemplateDetail(Base, TenantMixin, TimestampMixin):
    """Line item in Payment Terms Template."""

    __tablename__ = "payment_terms_template_details"

    detail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_terms_templates.template_id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_portion: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 30.00 for 30%
    due_date_based_on: Mapped[str] = mapped_column(String(64), nullable=False, default="Day(s) after invoice date")
    credit_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("PaymentTermsTemplate", back_populates="terms")


class PaymentSchedule(Base, TenantMixin, TimestampMixin):
    """Payment schedule installment linked to a Sales Invoice."""

    __tablename__ = "payment_schedules"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=False
    )
    payment_term: Mapped[str] = mapped_column(String(128), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    portion_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    portion_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNPAID")  # UNPAID, PARTIAL, PAID, OVERDUE

    sales_invoice = relationship("SalesInvoice")


# ==========================================
# 8. Multi-Tier Sales Taxes & Charges Templates
# ==========================================


class SalesTaxesAndChargesTemplate(Base, TenantMixin, TimestampMixin):
    """Standard multi-tier sales tax and charges template."""

    __tablename__ = "sales_taxes_and_charges_templates"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    tax_category: Mapped[str] = mapped_column(String(64), nullable=False, default="Standard")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    taxes: Mapped[list["SalesTaxesAndChargesTemplateDetail"]] = relationship(back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tax_template_title", "tenant_id", "title", unique=True),
    )


class SalesTaxesAndChargesTemplateDetail(Base, TenantMixin, TimestampMixin):
    """Line item in Sales Taxes and Charges Template."""

    __tablename__ = "sales_taxes_and_charges_template_details"

    detail_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_taxes_and_charges_templates.template_id"), nullable=False
    )
    charge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="On Net Total")  # Actual, On Net Total, On Previous Row Amount
    row_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_head: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., 2200-OUTPUT-VAT, 5100-FREIGHT
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))

    template = relationship("SalesTaxesAndChargesTemplate", back_populates="taxes")


# ==========================================
# 9. Customer Advance Payment Allocation
# ==========================================


class AdvancePaymentAllocation(Base, TenantMixin, TimestampMixin):
    """Allocation of Customer Advance Payment against an open Sales Invoice."""

    __tablename__ = "advance_payment_allocations"

    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=False
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    customer = relationship("Customer")
    sales_invoice = relationship("SalesInvoice")
