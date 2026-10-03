"""Fixed Asset Lifecycle and Depreciation Domain Models (ERPNext Parity)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class AssetCategory(Base, TenantMixin, TimestampMixin):
    """Asset Category master specifying default depreciation policies and GL accounts."""

    __tablename__ = "asset_categories"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_name: Mapped[str] = mapped_column(String(128), nullable=False)
    depreciation_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="STRAIGHT_LINE",  # STRAIGHT_LINE, DOUBLE_DECLINING, WRITTEN_DOWN_VALUE
    )
    total_number_of_depreciations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=36
    )
    frequency_in_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fixed_asset_account: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1500-FIXED-ASSETS"
    )
    accumulated_depreciation_account: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1550-ACCUMULATED-DEPRECIATION"
    )
    depreciation_expense_account: Mapped[str] = mapped_column(
        String(32), nullable=False, default="5200-DEP-MACHINERY"
    )

    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="category")

    __table_args__ = (
        Index("idx_asset_cat_tenant", "tenant_id", "category_name", unique=True),
    )


class AssetLocation(Base, TenantMixin, TimestampMixin):
    """Hierarchical physical asset location master."""

    __tablename__ = "asset_locations"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    location_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_locations.location_id"), nullable=True
    )

    __table_args__ = (
        Index("idx_asset_loc_tenant", "tenant_id", "location_name", unique=True),
    )


class Asset(Base, TenantMixin, TimestampMixin):
    """Core Fixed Asset registry tracking asset values, custodians, and lifecycle status."""

    __tablename__ = "assets"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_categories.category_id"), nullable=False
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_locations.location_id"), nullable=True
    )
    custodian_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, doc="Employee ID managing the asset"
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    available_for_use_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_purchase_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    salvage_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    current_book_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SUBMITTED, IN_USE, MAINTENANCE, SCRAPPED, SOLD
    )
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category: Mapped["AssetCategory"] = relationship("AssetCategory", back_populates="assets")
    schedules: Mapped[List["AssetDepreciationSchedule"]] = relationship(
        "AssetDepreciationSchedule", back_populates="asset", cascade="all, delete-orphan"
    )
    movements: Mapped[List["AssetMovement"]] = relationship(
        "AssetMovement", back_populates="asset", cascade="all, delete-orphan"
    )
    repairs: Mapped[List["AssetRepair"]] = relationship(
        "AssetRepair", back_populates="asset", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_asset_tenant_code", "tenant_id", "asset_code", unique=True),
        Index("idx_asset_tenant_status", "tenant_id", "status"),
    )


class AssetDepreciationSchedule(Base, TenantMixin, TimestampMixin):
    """Periodic schedule rows generated for asset depreciation amortization."""

    __tablename__ = "asset_depreciation_schedules"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False, index=True
    )
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    depreciation_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    book_value_after_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    is_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    asset: Mapped["Asset"] = relationship("Asset", back_populates="schedules")

    __table_args__ = (
        Index("idx_asset_dep_sched", "tenant_id", "asset_id", "schedule_date"),
    )


class AssetMovement(Base, TenantMixin, TimestampMixin):
    """Historical tracking of physical transfers and custodian handovers."""

    __tablename__ = "asset_movements"

    movement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False, index=True
    )
    from_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    to_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    from_custodian_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    to_custodian_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="movements")


class AssetRepair(Base, TenantMixin, TimestampMixin):
    """Maintenance repair events with optional cost capitalization into book value."""

    __tablename__ = "asset_repairs"

    repair_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False, index=True
    )
    repair_date: Mapped[date] = mapped_column(Date, nullable=False)
    repair_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    repair_description: Mapped[str] = mapped_column(Text, nullable=False)
    is_capitalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    asset: Mapped["Asset"] = relationship("Asset", back_populates="repairs")
