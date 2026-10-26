"""Buying, selling, shipping and loyalty master data for implementation Phase B."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class SupplierGroup(Base, TenantMixin, TimestampMixin):
    __tablename__ = "supplier_groups"
    supplier_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("supplier_groups.supplier_group_id"), nullable=True)
    lft: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rgt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "group_name", name="uq_supplier_group_tenant_name"), Index("ix_supplier_group_tenant_parent", "tenant_id", "parent_id"))


class PurchaseTaxesAndChargesTemplate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "purchase_taxes_and_charges_templates"
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    tax_category: Mapped[str] = mapped_column(String(64), nullable=False, default="Standard")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    taxes: Mapped[list["PurchaseTaxesAndChargesTemplateDetail"]] = relationship(back_populates="template", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "title", name="uq_purchase_tax_template_tenant_title"),)


class PurchaseTaxesAndChargesTemplateDetail(Base, TenantMixin, TimestampMixin):
    __tablename__ = "purchase_taxes_and_charges_template_details"
    detail_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_taxes_and_charges_templates.template_id", ondelete="CASCADE"), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="On Net Total")
    row_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_head: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    reference_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    included_in_rate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    add_deduct: Mapped[str] = mapped_column(String(8), nullable=False, default="ADD")
    consider_for_valuation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("rate >= 0", name="ck_purchase_tax_rate_nonnegative"), CheckConstraint("charge_type IN ('Actual','On Net Total','On Previous Row Amount','On Previous Row Total','On Item Quantity')", name="ck_purchase_tax_charge_type"), CheckConstraint("add_deduct IN ('ADD','DEDUCT')", name="ck_purchase_tax_add_deduct"), Index("ix_purchase_tax_detail_tenant_template", "tenant_id", "template_id"))
    template: Mapped[PurchaseTaxesAndChargesTemplate] = relationship(back_populates="taxes")


class ShippingRule(Base, TenantMixin, TimestampMixin):
    __tablename__ = "shipping_rules"
    shipping_rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conditions: Mapped[list["ShippingRuleCondition"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "rule_name", name="uq_shipping_rule_tenant_name"), Index("ix_shipping_rule_tenant_priority", "tenant_id", "priority"))


class ShippingRuleCondition(Base, TenantMixin, TimestampMixin):
    __tablename__ = "shipping_rule_conditions"
    condition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipping_rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_rules.shipping_rule_id", ondelete="CASCADE"), nullable=False)
    based_on: Mapped[str] = mapped_column(String(32), nullable=False, default="ORDER_VALUE")
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    charge_type: Mapped[str] = mapped_column(String(16), nullable=False, default="FIXED")
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    __table_args__ = (CheckConstraint("based_on IN ('ORDER_VALUE','WEIGHT','ITEM_QTY')", name="ck_shipping_condition_based_on"), CheckConstraint("charge_type IN ('FIXED','PER_UNIT','PERCENT')", name="ck_shipping_condition_charge_type"), CheckConstraint("rate >= 0", name="ck_shipping_condition_rate_nonnegative"), CheckConstraint("max_value IS NULL OR min_value IS NULL OR max_value >= min_value", name="ck_shipping_condition_range"), Index("ix_shipping_condition_tenant_rule", "tenant_id", "shipping_rule_id"))
    rule: Mapped[ShippingRule] = relationship(back_populates="conditions")


class ItemManufacturer(Base, TenantMixin, TimestampMixin):
    __tablename__ = "item_manufacturers"
    item_manufacturer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False)
    manufacturer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_part_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "item_id", "manufacturer_name", name="uq_item_manufacturer_tenant_item_name"), Index("ix_item_manufacturer_tenant_item", "tenant_id", "item_id"))


class PromotionalScheme(Base, TenantMixin, TimestampMixin):
    __tablename__ = "promotional_schemes"
    scheme_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scheme_type: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOUNT")
    discount_type: Mapped[str] = mapped_column(String(16), nullable=False, default="PERCENT")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    buy_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    free_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id", ondelete="CASCADE"), nullable=True)
    free_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=True)
    item_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_groups.item_group_id", ondelete="CASCADE"), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "scheme_name", name="uq_promo_scheme_tenant_name"), CheckConstraint("scheme_type IN ('DISCOUNT','BUY_X_GET_Y')", name="ck_promo_scheme_type"), CheckConstraint("discount_type IN ('PERCENT','FIXED')", name="ck_promo_discount_type"), CheckConstraint("discount_value >= 0 AND (discount_type <> 'PERCENT' OR discount_value <= 100)", name="ck_promo_discount_nonnegative"), CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_promo_dates"), CheckConstraint("scheme_type <> 'BUY_X_GET_Y' OR (buy_quantity IS NOT NULL AND buy_quantity > 0 AND free_quantity IS NOT NULL AND free_quantity > 0)", name="ck_promo_buy_get_quantities"))


class PricingRule(Base, TenantMixin, TimestampMixin):
    __tablename__ = "pricing_rules"
    pricing_rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.item_id", ondelete="CASCADE"), nullable=True)
    item_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_groups.item_group_id", ondelete="CASCADE"), nullable=True)
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.price_list_id", ondelete="CASCADE"), nullable=True)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("1.0000"))
    discount_type: Mapped[str] = mapped_column(String(16), nullable=False, default="PERCENT")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "rule_name", name="uq_pricing_rule_tenant_name"), CheckConstraint("discount_type IN ('PERCENT','FIXED')", name="ck_pricing_rule_discount_type"), CheckConstraint("min_quantity > 0 AND discount_value >= 0 AND (discount_type <> 'PERCENT' OR discount_value <= 100)", name="ck_pricing_rule_values"), CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_pricing_rule_dates"), Index("ix_pricing_rule_tenant_priority", "tenant_id", "priority"))


class SalesPartner(Base, TenantMixin, TimestampMixin):
    __tablename__ = "sales_partners"
    sales_partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("0.0000"))
    territory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "partner_name", name="uq_sales_partner_tenant_name"), CheckConstraint("commission_rate BETWEEN 0 AND 100", name="ck_sales_partner_commission_range"))


class SalesTeam(Base, TenantMixin, TimestampMixin):
    __tablename__ = "sales_teams"
    sales_team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sales_partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_partners.sales_partner_id", ondelete="CASCADE"), nullable=False)
    contribution_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("100.0000"))
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "document_type", "document_id", "sales_partner_id", name="uq_sales_team_document_partner"), CheckConstraint("contribution_pct BETWEEN 0 AND 100", name="ck_sales_team_contribution_range"), CheckConstraint("commission_rate IS NULL OR commission_rate BETWEEN 0 AND 100", name="ck_sales_team_commission_range"), Index("ix_sales_team_tenant_document", "tenant_id", "document_type", "document_id"))


class LoyaltyProgram(Base, TenantMixin, TimestampMixin):
    __tablename__ = "loyalty_programs"
    loyalty_program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_name: Mapped[str] = mapped_column(String(128), nullable=False)
    points_per_currency: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("1.000000"))
    redemption_value_per_point: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0.010000"))
    minimum_redemption_points: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "program_name", name="uq_loyalty_program_tenant_name"), CheckConstraint("points_per_currency >= 0 AND redemption_value_per_point > 0 AND minimum_redemption_points >= 0", name="ck_loyalty_program_values"))


class LoyaltyPointEntry(Base, TenantMixin, TimestampMixin):
    __tablename__ = "loyalty_point_entries"
    loyalty_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loyalty_program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loyalty_programs.loyalty_program_id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    points: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (CheckConstraint("entry_type IN ('EARN','REDEEM')", name="ck_loyalty_entry_type"), CheckConstraint("points > 0", name="ck_loyalty_entry_points_positive"), UniqueConstraint("tenant_id", "loyalty_program_id", "customer_id", "invoice_id", "entry_type", name="uq_loyalty_invoice_entry"), Index("ix_loyalty_entry_tenant_customer_date", "tenant_id", "customer_id", "posting_date"))
