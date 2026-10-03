"""Logistics and Order Fulfillment Domain Models (Pick Lists, Packing Slips, Delivery Trips)."""

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
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class PickList(Base, TenantMixin, TimestampMixin):
    """Warehouse Pick List for order picking and staging."""

    __tablename__ = "pick_lists"

    pick_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pick_list_number: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DELIVERY"
    )  # DELIVERY, MATERIAL_TRANSFER, MANUFACTURE
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, PICKING, COMPLETED, CANCELLED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["PickListItem"]] = relationship(
        back_populates="pick_list", cascade="all, delete-orphan"
    )
    customer = relationship("Customer")

    __table_args__ = (
        Index("idx_pl_tenant_number", "tenant_id", "pick_list_number", unique=True),
    )


class PickListItem(Base, TenantMixin, TimestampMixin):
    """Line item in a warehouse pick list."""

    __tablename__ = "pick_list_items"

    pick_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pick_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pick_lists.pick_list_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=False
    )
    qty_to_pick: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    picked_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    source_document_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SALES_ORDER, MATERIAL_REQUEST
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(64), nullable=True)

    pick_list: Mapped["PickList"] = relationship(back_populates="items")
    item = relationship("Item")
    warehouse = relationship("Warehouse")


class PackingSlip(Base, TenantMixin, TimestampMixin):
    """Packaging carton or crate manifest linked to a Delivery Note."""

    __tablename__ = "packing_slips"

    packing_slip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slip_number: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_notes.delivery_note_id"), nullable=True
    )
    from_case_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    to_case_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    net_weight_pkg: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    gross_weight_pkg: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, SUBMITTED, CANCELLED

    items: Mapped[list["PackingSlipItem"]] = relationship(
        back_populates="packing_slip", cascade="all, delete-orphan"
    )
    delivery_note = relationship("DeliveryNote")

    __table_args__ = (
        Index("idx_ps_tenant_number", "tenant_id", "slip_number", unique=True),
    )


class PackingSlipItem(Base, TenantMixin, TimestampMixin):
    """Item packed into a specific carton case."""

    __tablename__ = "packing_slip_items"

    slip_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    packing_slip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packing_slips.packing_slip_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    net_weight: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    packing_slip: Mapped["PackingSlip"] = relationship(back_populates="items")
    item = relationship("Item")


class DeliveryTrip(Base, TenantMixin, TimestampMixin):
    """Multi-stop dispatch vehicle route for order distribution."""

    __tablename__ = "delivery_trips"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trip_number: Mapped[str] = mapped_column(String(64), nullable=False)
    driver_name: Mapped[str] = mapped_column(String(128), nullable=False)
    vehicle_number: Mapped[str] = mapped_column(String(64), nullable=False)
    departure_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, IN_TRANSIT, COMPLETED, CANCELLED
    total_distance_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    stops: Mapped[list["DeliveryStop"]] = relationship(
        back_populates="delivery_trip",
        cascade="all, delete-orphan",
        order_by="DeliveryStop.stop_sequence",
    )

    __table_args__ = (
        Index("idx_dt_tenant_number", "tenant_id", "trip_number", unique=True),
    )


class DeliveryStop(Base, TenantMixin, TimestampMixin):
    """Customer destination stop along a delivery trip."""

    __tablename__ = "delivery_stops"

    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_trips.trip_id"), nullable=False
    )
    delivery_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_notes.delivery_note_id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING, ARRIVED, DELIVERED, FAILED
    arrival_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)

    delivery_trip: Mapped["DeliveryTrip"] = relationship(back_populates="stops")
    delivery_note = relationship("DeliveryNote")
    customer = relationship("Customer")
