"""Purchasing and Accounts Payable Domain Models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Supplier(Base, TenantMixin, TimestampMixin):
    """Vendor master directory."""

    __tablename__ = "suppliers"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    supplier_code: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    otif_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00"), doc="On-time in-full score %"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_sup_tenant_code", "tenant_id", "supplier_code", unique=True),)


class PurchaseOrder(Base, TenantMixin, TimestampMixin):
    """Purchase Order records."""

    __tablename__ = "purchase_orders"

    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    po_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SUBMITTED, PARTIALLY_RECEIVED, COMPLETED, CANCELLED
    )

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_po_tenant_number", "tenant_id", "po_number", unique=True),)


class PurchaseOrderItem(Base, TenantMixin, TimestampMixin):
    """Individual line items within a Purchase Order."""

    __tablename__ = "purchase_order_items"

    item_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class GoodsReceiptNote(Base, TenantMixin, TimestampMixin):
    """Warehouse delivery receipt note."""

    __tablename__ = "goods_receipt_notes"

    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grn_number: Mapped[str] = mapped_column(String(64), nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")

    items: Mapped[list["GoodsReceiptNoteItem"]] = relationship(
        back_populates="grn", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_grn_tenant_number", "tenant_id", "grn_number", unique=True),)


class GoodsReceiptNoteItem(Base, TenantMixin, TimestampMixin):
    """Line items for warehouse delivery receipt note."""

    __tablename__ = "goods_receipt_note_items"

    grn_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipt_notes.grn_id"), nullable=False
    )
    po_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_order_items.item_line_id"), nullable=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    grn: Mapped["GoodsReceiptNote"] = relationship(back_populates="items")


class SupplierInvoice(Base, TenantMixin, TimestampMixin):
    """Supplier invoice subject to automated 3-way matching."""

    __tablename__ = "supplier_invoices"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=True
    )
    grn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipt_notes.grn_id"), nullable=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    matching_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="UNMATCHED",  # UNMATCHED, MATCHED, DISPUTED, STAGED, POSTED
    )
    variance_percentage: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.0000")
    )
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["SupplierInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sinv_tenant_number", "tenant_id", "supplier_id", "invoice_number", unique=True),
    )


class SupplierInvoiceItem(Base, TenantMixin, TimestampMixin):
    """Itemized line within a vendor supplier invoice."""

    __tablename__ = "supplier_invoice_items"

    invoice_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_invoices.invoice_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=True
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    invoice: Mapped["SupplierInvoice"] = relationship(back_populates="items")

