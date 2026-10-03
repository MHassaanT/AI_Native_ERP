"""Subcontracting Domain Models with Complete ERPNext Parity."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class SubcontractingOrder(Base, TenantMixin, TimestampMixin):
    """Subcontracting Order for tracking components supplied to external manufacturing vendors."""

    __tablename__ = "subcontracting_orders"

    sco_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sco_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    service_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, IN_PROCESS, COMPLETED, CANCELLED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["SubcontractingOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    supplied_items: Mapped[list["SubcontractingSuppliedItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")
    purchase_order = relationship("PurchaseOrder")

    __table_args__ = (
        Index("idx_sco_tenant_number", "tenant_id", "sco_number", unique=True),
    )


class SubcontractingOrderItem(Base, TenantMixin, TimestampMixin):
    """Finished goods produced by the subcontractor."""

    __tablename__ = "subcontracting_order_items"

    sco_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sco_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontracting_orders.sco_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    order: Mapped["SubcontractingOrder"] = relationship(back_populates="items")
    item = relationship("Item")


class SubcontractingSuppliedItem(Base, TenantMixin, TimestampMixin):
    """Raw materials and parts transferred to subcontractor warehouse for assembly/processing."""

    __tablename__ = "subcontracting_supplied_items"

    supplied_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sco_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontracting_orders.sco_id"), nullable=False
    )
    raw_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    required_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    supplied_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    consumed_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    supplier_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )

    order: Mapped["SubcontractingOrder"] = relationship(back_populates="supplied_items")
    raw_item = relationship("Item", foreign_keys=[raw_item_id])
    source_warehouse = relationship("Warehouse", foreign_keys=[source_warehouse_id])
    supplier_warehouse = relationship("Warehouse", foreign_keys=[supplier_warehouse_id])


class SubcontractingReceipt(Base, TenantMixin, TimestampMixin):
    """Receipt of processed/finished goods from subcontractor."""

    __tablename__ = "subcontracting_receipts"

    scr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scr_number: Mapped[str] = mapped_column(String(64), nullable=False)
    sco_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontracting_orders.sco_id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    target_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="COMPLETED"
    )

    items: Mapped[list["SubcontractingReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )
    order = relationship("SubcontractingOrder")
    supplier = relationship("Supplier")
    target_warehouse = relationship("Warehouse")

    __table_args__ = (
        Index("idx_scr_tenant_number", "tenant_id", "scr_number", unique=True),
    )


class SubcontractingReceiptItem(Base, TenantMixin, TimestampMixin):
    """Finished goods item line in a subcontracting receipt."""

    __tablename__ = "subcontracting_receipt_items"

    scr_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontracting_receipts.scr_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    service_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    receipt: Mapped["SubcontractingReceipt"] = relationship(back_populates="items")
    item = relationship("Item")
