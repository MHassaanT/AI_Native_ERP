"""Inventory and Stock Domain Models replacing legacy tabStock Ledger Entry."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Item(Base, TenantMixin, TimestampMixin):
    """Product and material master catalog."""

    __tablename__ = "items"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_uom: Mapped[str] = mapped_column(String(32), nullable=False, default="Nos")
    is_stock_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_sales_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_purchase_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valuation_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="FIFO",  # FIFO, Moving Average, Standard
    )
    standard_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Variant & Serial/Batch Extensions
    has_variants: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variant_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=True
    )
    variant_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    has_batch_no: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_serial_no: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent_item = relationship("Item", remote_side=[item_id])

    __table_args__ = (Index("idx_item_tenant_code", "tenant_id", "item_code", unique=True),)


class Warehouse(Base, TenantMixin, TimestampMixin):
    """Physical and virtual inventory locations."""

    __tablename__ = "warehouses"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_code: Mapped[str] = mapped_column(String(64), nullable=False)
    warehouse_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_quarantine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_wh_tenant_code", "tenant_id", "warehouse_code", unique=True),)


class StockLedgerEntry(Base, TenantMixin):
    """Immutable append-only Stock Ledger Entry table."""

    __tablename__ = "stock_ledger_entries"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    posting_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False, index=True
    )
    actual_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, doc="Delta movement (+ve inbound, -ve outbound)"
    )
    qty_after_transaction: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    incoming_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    outgoing_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    valuation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    stock_value_difference: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    source_document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="GOODS_RECEIPT, DELIVERY_NOTE, WORK_ORDER_ISSUE, STOCK_ENTRY, STOCK_RECONCILIATION"
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_sle_item_wh_datetime", "tenant_id", "item_id", "warehouse_id", "posting_datetime"
        ),
    )


class StockLevel(Base, TenantMixin, TimestampMixin):
    """Current stock level cache per item and warehouse."""

    __tablename__ = "stock_levels"

    stock_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    current_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    reserved_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    available_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    valuation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    lot_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    item = relationship("Item")
    warehouse = relationship("Warehouse")

    __table_args__ = (
        Index(
            "idx_stock_level_tenant_item_wh", "tenant_id", "item_id", "warehouse_id", unique=True
        ),
    )


class Batch(Base, TenantMixin, TimestampMixin):
    """Lot or batch tracking with manufacturing and expiration control."""

    __tablename__ = "batches"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    manufacturing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ACTIVE, EXPIRED, RECALLED
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    item = relationship("Item")

    __table_args__ = (
        Index("idx_batch_tenant_num", "tenant_id", "batch_number", unique=True),
    )


class SerialNo(Base, TenantMixin, TimestampMixin):
    """Unit-level serial number lifecycle tracking."""

    __tablename__ = "serial_numbers"

    serial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ACTIVE, DELIVERED, EXPIRED, MAINTENANCE
    purchase_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purchase_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    delivery_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    item = relationship("Item")
    warehouse = relationship("Warehouse")

    __table_args__ = (
        Index("idx_serial_tenant_num", "tenant_id", "serial_number", unique=True),
    )


class StockEntry(Base, TenantMixin, TimestampMixin):
    """Universal stock movement document (Receipt, Issue, Transfer, Manufacture, Repack)."""

    __tablename__ = "stock_entries"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_number: Mapped[str] = mapped_column(String(64), nullable=False)
    stock_entry_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="MATERIAL_TRANSFER"
    )  # MATERIAL_RECEIPT, MATERIAL_ISSUE, MATERIAL_TRANSFER, MANUFACTURE, REPACK
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    posting_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=lambda: datetime.now().time()
    )
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    to_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, SUBMITTED, CANCELLED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["StockEntryItem"]] = relationship(
        back_populates="stock_entry", cascade="all, delete-orphan"
    )
    from_warehouse = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = relationship("Warehouse", foreign_keys=[to_warehouse_id])

    __table_args__ = (
        Index("idx_se_tenant_number", "tenant_id", "entry_number", unique=True),
    )


class StockEntryItem(Base, TenantMixin, TimestampMixin):
    """Line item in a universal Stock Entry movement."""

    __tablename__ = "stock_entry_items"

    entry_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_entries.entry_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    s_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    t_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    uom: Mapped[str] = mapped_column(String(32), nullable=False, default="Nos")
    basic_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(64), nullable=True)

    stock_entry: Mapped["StockEntry"] = relationship(back_populates="items")
    item = relationship("Item")
    source_warehouse = relationship("Warehouse", foreign_keys=[s_warehouse_id])
    target_warehouse = relationship("Warehouse", foreign_keys=[t_warehouse_id])


class StockReconciliation(Base, TenantMixin, TimestampMixin):
    """Physical count reconciliation voucher adjusting book inventory."""

    __tablename__ = "stock_reconciliations"

    reconciliation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reconciliation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    posting_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=lambda: datetime.now().time()
    )
    purpose: Mapped[str] = mapped_column(
        String(64), nullable=False, default="STOCK_RECONCILIATION"
    )  # STOCK_RECONCILIATION, OPENING_STOCK
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, SUBMITTED, CANCELLED
    total_variance_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    expense_account: Mapped[str] = mapped_column(
        String(64), nullable=False, default="5200-STOCK-ADJUSTMENT"
    )

    items: Mapped[list["StockReconciliationItem"]] = relationship(
        back_populates="reconciliation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sr_tenant_number", "tenant_id", "reconciliation_number", unique=True),
    )


class StockReconciliationItem(Base, TenantMixin, TimestampMixin):
    """Physical count line adjusting a specific item and warehouse."""

    __tablename__ = "stock_reconciliation_items"

    recon_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_reconciliations.reconciliation_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    current_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    reconciled_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    difference_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    current_valuation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    reconciled_valuation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    difference_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    reconciliation: Mapped["StockReconciliation"] = relationship(back_populates="items")
    item = relationship("Item")
    warehouse = relationship("Warehouse")


class StockReservationEntry(Base, TenantMixin, TimestampMixin):
    """Inventory reservation locks against Sales Orders or Material Requests."""

    __tablename__ = "stock_reservation_entries"

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    voucher_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="SALES_ORDER"
    )  # SALES_ORDER, MATERIAL_REQUEST
    voucher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reserved_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    consumed_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ACTIVE, FULFILLED, CANCELLED

    item = relationship("Item")
    warehouse = relationship("Warehouse")

    __table_args__ = (
        Index("idx_sre_tenant_voucher", "tenant_id", "voucher_type", "voucher_id"),
    )


class ItemAttribute(Base, TenantMixin, TimestampMixin):
    """Product variant attribute specification (Size, Color, Material)."""

    __tablename__ = "item_attributes"

    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attribute_name: Mapped[str] = mapped_column(String(64), nullable=False)

    values: Mapped[list["ItemAttributeValue"]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_ia_tenant_name", "tenant_id", "attribute_name", unique=True),
    )


class ItemAttributeValue(Base, TenantMixin, TimestampMixin):
    """Allowed value for a product variant attribute."""

    __tablename__ = "item_attribute_values"

    value_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_attributes.attribute_id"), nullable=False
    )
    attribute_value: Mapped[str] = mapped_column(String(64), nullable=False)
    abbr: Mapped[str | None] = mapped_column(String(16), nullable=True)

    attribute: Mapped["ItemAttribute"] = relationship(back_populates="values")
