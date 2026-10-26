"""Tenant-scoped shared master data used across ERP modules."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class ItemGroup(Base, TenantMixin, TimestampMixin):
    __tablename__ = "item_groups"
    item_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_groups.item_group_id"), nullable=True)
    lft: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rgt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parent: Mapped["ItemGroup | None"] = relationship(remote_side="ItemGroup.item_group_id")
    __table_args__ = (UniqueConstraint("tenant_id", "group_name", name="uq_item_group_tenant_name"), Index("ix_item_group_tenant_parent", "tenant_id", "parent_id"))


class PriceList(Base, TenantMixin, TimestampMixin):
    __tablename__ = "price_lists"
    price_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_list_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    selling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    buying: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "price_list_name", name="uq_price_list_tenant_name"), CheckConstraint("selling OR buying", name="ck_price_list_has_context"))


class ItemPrice(Base, TenantMixin, TimestampMixin):
    __tablename__ = "item_prices"
    item_price_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False)
    price_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.price_list_id", ondelete="CASCADE"), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id"), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "item_id", "price_list_id", "uom_id", "currency", "valid_from", name="uq_item_price_period"), CheckConstraint("rate >= 0", name="ck_item_price_nonnegative"), CheckConstraint("priority >= 0", name="ck_item_price_priority_nonnegative"), Index("ix_item_price_tenant_list_item", "tenant_id", "price_list_id", "item_id"))


class Contact(Base, TenantMixin, TimestampMixin):
    __tablename__ = "contacts"
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    link_doctype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    link_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (Index("ix_contact_tenant_dynamic_link", "tenant_id", "link_doctype", "link_name"), Index("ix_contact_tenant_email", "tenant_id", "email"))


class Address(Base, TenantMixin, TimestampMixin):
    __tablename__ = "addresses"
    address_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address_title: Mapped[str] = mapped_column(String(255), nullable=False)
    address_type: Mapped[str] = mapped_column(String(32), nullable=False, default="BILLING")
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    link_doctype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    link_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("address_type IN ('BILLING','SHIPPING','OFFICE','OTHER')", name="ck_address_type"), Index("ix_address_tenant_dynamic_link", "tenant_id", "link_doctype", "link_name"))


class UOM(Base, TenantMixin, TimestampMixin):
    __tablename__ = "uoms"
    uom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uom_name: Mapped[str] = mapped_column(String(64), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "uom_name", name="uq_uom_tenant_name"), UniqueConstraint("tenant_id", "abbreviation", name="uq_uom_tenant_abbreviation"))


class UOMConversion(Base, TenantMixin, TimestampMixin):
    __tablename__ = "uom_conversions"
    conversion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_uom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id", ondelete="CASCADE"), nullable=False)
    to_uom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id", ondelete="CASCADE"), nullable=False)
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id", ondelete="CASCADE"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "from_uom_id", "to_uom_id", "item_id", name="uq_uom_conversion"), CheckConstraint("factor > 0", name="ck_uom_conversion_positive"), CheckConstraint("from_uom_id <> to_uom_id", name="ck_uom_conversion_distinct"))


class NamingSeries(Base, TenantMixin, TimestampMixin):
    __tablename__ = "naming_series"
    naming_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    current_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    number_width: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "document_type", "prefix", name="uq_naming_series_tenant_doc_prefix"), CheckConstraint("current_number >= 0", name="ck_naming_series_nonnegative"), CheckConstraint("number_width BETWEEN 1 AND 12", name="ck_naming_series_width"))


class TermsAndConditionsTemplate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "terms_and_conditions_templates"
    terms_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    terms: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_to: Mapped[str] = mapped_column(String(32), nullable=False, default="BOTH")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "template_name", name="uq_terms_template_tenant_name"), CheckConstraint("applicable_to IN ('BUYING','SELLING','BOTH')", name="ck_terms_template_applicable"))


class ProductBundle(Base, TenantMixin, TimestampMixin):
    __tablename__ = "product_bundles"
    bundle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False)
    bundle_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    items: Mapped[list["ProductBundleItem"]] = relationship(back_populates="bundle", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "bundle_item_id", name="uq_product_bundle_item"),)


class ProductBundleItem(Base, TenantMixin, TimestampMixin):
    __tablename__ = "product_bundle_items"
    bundle_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_bundles.bundle_id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id"), nullable=True)
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_product_bundle_item_quantity"), UniqueConstraint("tenant_id", "bundle_id", "item_id", name="uq_product_bundle_component"))
    bundle: Mapped[ProductBundle] = relationship(back_populates="items")


class IssueType(Base, TenantMixin, TimestampMixin):
    __tablename__ = "issue_types"
    issue_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "type_name", name="uq_issue_type_tenant_name"),)
