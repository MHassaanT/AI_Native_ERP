"""Sales and Revenue Domain Models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
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
    lifetime_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_cust_tenant_code", "tenant_id", "customer_code", unique=True),)


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
    contribution_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("22.00"), doc="Guarded margin percentage"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED
    )

    __table_args__ = (
        Index("idx_quote_tenant_number", "tenant_id", "quotation_number", unique=True),
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

    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="sales_order", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_so_tenant_number", "tenant_id", "order_number", unique=True),)


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
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    sales_order: Mapped["SalesOrder"] = relationship(back_populates="items")


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

    sales_invoice: Mapped["SalesInvoice"] = relationship(back_populates="items")

