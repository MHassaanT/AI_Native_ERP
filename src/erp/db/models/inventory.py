"""Inventory and Stock Domain Models replacing legacy tabStock Ledger Entry."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
        String(64), nullable=False, doc="GOODS_RECEIPT, DELIVERY_NOTE, WORK_ORDER_ISSUE"
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    __table_args__ = (
        Index(
            "idx_stock_level_tenant_item_wh", "tenant_id", "item_id", "warehouse_id", unique=True
        ),
    )

