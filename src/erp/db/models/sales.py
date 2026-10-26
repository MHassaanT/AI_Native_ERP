"""Sales and Revenue Domain Models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Customer(Base, TenantMixin, TimestampMixin):
    """Customer profile master."""

    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_code: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("10000.0000")
    )
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    lifetime_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_cust_tenant_code", "tenant_id", "customer_code", unique=True),
        CheckConstraint("payment_terms_days BETWEEN 0 AND 3650", name="ck_customer_payment_terms_days"),
    )


class SalesQuotation(Base, TenantMixin, TimestampMixin):
    """Dynamic quotation evaluated by Revenue Agent."""

    __tablename__ = "sales_quotations"

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quotation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.price_list_id"), nullable=True)
    shipping_rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_rules.shipping_rule_id"), nullable=True)
    sales_tax_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_taxes_and_charges_templates.template_id"), nullable=True)
    tax_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    shipping_charge: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    calculation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contribution_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("22.00"), doc="Guarded margin percentage"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED
    )
    items: Mapped[list["SalesQuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_quote_tenant_number", "tenant_id", "quotation_number", unique=True),
    )


class SalesQuotationItem(Base, TenantMixin, TimestampMixin):
    """Commercial line snapshot on a customer quotation."""

    __tablename__ = "sales_quotation_items"

    quotation_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_quotations.quotation_id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id"), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.price_list_id"), nullable=True)
    item_price_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_prices.item_price_id"), nullable=True)
    price_list_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pricing_rules.pricing_rule_id"), nullable=True)
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("promotional_schemes.scheme_id"), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bundle_components_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    quotation: Mapped["SalesQuotation"] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_sales_quotation_item_tenant_quote", "tenant_id", "quotation_id"),
        CheckConstraint("quantity > 0", name="ck_sales_quotation_item_quantity_positive"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_sales_quotation_item_amounts_nonnegative"),
        CheckConstraint("discount_amount >= 0", name="ck_sales_quotation_item_discount_nonnegative"),
        CheckConstraint("conversion_factor > 0 AND stock_quantity >= 0", name="ck_sales_quotation_item_uom_positive"),
    )


class SalesOrder(Base, TenantMixin, TimestampMixin):
    """Confirmed customer Sales Order."""

    __tablename__ = "sales_orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")
    amended_from_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.order_id"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfillment_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    source_quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_quotations.quotation_id"), nullable=True
    )
    customer_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.contact_id"), nullable=True
    )
    customer_contact_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    billing_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=True
    )
    billing_address_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    shipping_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=True
    )
    shipping_address_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    terms_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms_and_conditions_templates.terms_template_id"), nullable=True
    )
    sales_tax_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_taxes_and_charges_templates.template_id"), nullable=True)
    tax_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.price_list_id"), nullable=True
    )
    shipping_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipping_rules.shipping_rule_id"), nullable=True
    )
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1.00000000"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    taxes_and_charges: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    shipping_charge: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    calculation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="sales_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_so_tenant_number", "tenant_id", "order_number", unique=True),
        Index("ix_sales_order_tenant_source_quotation", "tenant_id", "source_quotation_id"),
        CheckConstraint("exchange_rate > 0", name="ck_sales_order_exchange_rate_positive"),
        CheckConstraint("discount_amount >= 0", name="ck_sales_order_discount_nonnegative"),
    )


class SalesOrderItem(Base, TenantMixin, TimestampMixin):
    """Sales Order line item."""

    __tablename__ = "sales_order_items"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.order_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    source_quotation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_quotation_items.quotation_item_id"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id"), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1.00000000"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    invoiced_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.price_list_id"), nullable=True)
    item_price_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_prices.item_price_id"), nullable=True)
    price_list_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pricing_rules.pricing_rule_id"), nullable=True)
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("promotional_schemes.scheme_id"), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bundle_components_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    sales_order: Mapped["SalesOrder"] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("conversion_factor > 0", name="ck_sales_order_item_conversion_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_sales_order_item_stock_quantity_nonnegative"),
        CheckConstraint("delivered_quantity >= 0", name="ck_sales_order_item_delivered_nonnegative"),
        CheckConstraint("invoiced_quantity >= 0", name="ck_sales_order_item_invoiced_nonnegative"),
        CheckConstraint("returned_quantity >= 0", name="ck_sales_order_item_returned_nonnegative"),
        CheckConstraint("discount_amount >= 0", name="ck_sales_order_item_discount_nonnegative"),
    )


class DeliveryNote(Base, TenantMixin, TimestampMixin):
    """Customer order delivery and warehouse fulfillment note."""

    __tablename__ = "delivery_notes"

    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_note_number: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.order_id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISPATCHED")

    sales_order: Mapped["SalesOrder"] = relationship()
    customer: Mapped["Customer"] = relationship()
    items: Mapped[list["DeliveryNoteItem"]] = relationship(
        back_populates="delivery_note", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_dn_tenant_number", "tenant_id", "delivery_note_number", unique=True),
    )


class DeliveryNoteItem(Base, TenantMixin, TimestampMixin):
    """Fulfilled line item in Delivery Note."""

    __tablename__ = "delivery_note_items"

    dn_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_notes.delivery_note_id"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_order_items.order_item_id"), nullable=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    cost_unit_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cost_valuation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cost_source: Mapped[str | None] = mapped_column(String(48), nullable=True)
    cost_source_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cost_is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bundle_components_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    delivery_note: Mapped["DeliveryNote"] = relationship(back_populates="items")


class SalesInvoice(Base, TenantMixin, TimestampMixin):
    """Customer Sales Invoice generating Accounts Receivable."""

    __tablename__ = "sales_invoices"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.order_id"), nullable=True
    )
    delivery_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_notes.delivery_note_id"), nullable=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ISSUED",  # ISSUED, PAID, CANCELLED
    )

    customer: Mapped["Customer"] = relationship()
    sales_order: Mapped["SalesOrder | None"] = relationship()
    delivery_note: Mapped["DeliveryNote | None"] = relationship()
    items: Mapped[list["SalesInvoiceItem"]] = relationship(
        back_populates="sales_invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sinv_cust_number", "tenant_id", "invoice_number", unique=True),
    )


class SalesInvoiceItem(Base, TenantMixin, TimestampMixin):
    """Line item on customer Sales Invoice."""

    __tablename__ = "sales_invoice_items"

    invoice_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.invoice_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_order_items.order_item_id"), nullable=True
    )
    delivery_note_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_note_items.dn_item_id"), nullable=True
    )
    stock_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cost_unit_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    cost_valuation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cost_source: Mapped[str | None] = mapped_column(String(48), nullable=True)
    cost_source_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cost_is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bundle_components_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    sales_invoice: Mapped["SalesInvoice"] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_sales_invoice_item_tenant_order_item", "tenant_id", "order_item_id"),
        Index("ix_sales_invoice_item_tenant_dn_item", "tenant_id", "delivery_note_item_id"),
    )
