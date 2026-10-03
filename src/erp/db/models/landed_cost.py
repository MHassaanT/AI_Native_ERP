"""Landed Cost Voucher Domain Models with Complete ERPNext Parity."""

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


class LandedCostVoucher(Base, TenantMixin, TimestampMixin):
    """Landed Cost Voucher for capitalizing shipping, customs, and port charges into inventory."""

    __tablename__ = "landed_cost_vouchers"

    lcv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    voucher_number: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    company: Mapped[str] = mapped_column(String(128), nullable=False, default="Corporate")
    distribute_charges_based_on: Mapped[str] = mapped_column(
        String(32), nullable=False, default="VALUATION"  # VALUATION, QUANTITY, WEIGHT, VOLUME
    )
    total_charges: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, CANCELLED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["LandedCostItem"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )
    taxes_and_charges: Mapped[list["LandedCostTaxesAndCharges"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_lcv_tenant_number", "tenant_id", "voucher_number", unique=True),
    )


class LandedCostTaxesAndCharges(Base, TenantMixin, TimestampMixin):
    """Applicable freight, duty, or handling charge line in a Landed Cost Voucher."""

    __tablename__ = "landed_cost_taxes_and_charges"

    charge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lcv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landed_cost_vouchers.lcv_id"), nullable=False
    )
    expense_account: Mapped[str] = mapped_column(
        String(64), nullable=False, default="5100-FREIGHT-CUSTOMS-CLEARING"
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    voucher: Mapped["LandedCostVoucher"] = relationship(back_populates="taxes_and_charges")


class LandedCostItem(Base, TenantMixin, TimestampMixin):
    """Item received in a GRN receiving allocated landed costs."""

    __tablename__ = "landed_cost_items"

    lcv_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lcv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landed_cost_vouchers.lcv_id"), nullable=False
    )
    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipt_notes.grn_id"), nullable=False
    )
    grn_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipt_note_items.grn_item_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    purchase_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    purchase_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    applicable_charges: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    new_valuation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    voucher: Mapped["LandedCostVoucher"] = relationship(back_populates="items")
    item = relationship("Item")
    grn = relationship("GoodsReceiptNote")
