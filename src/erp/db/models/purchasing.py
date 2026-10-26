"""Purchasing and Accounts Payable Domain Models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    supplier_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("supplier_groups.supplier_group_id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_group = relationship("SupplierGroup")

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
    amended_from_po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Commercial snapshot fields are intentionally copied onto the document.
    # A future master-data edit must never alter a submitted purchase order.
    material_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_requests.mr_id"), nullable=True
    )
    supplier_quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_quotations.sq_id", name="fk_purchase_orders_supplier_quotation"), nullable=True
    )
    required_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.project_id", name="fk_purchase_orders_project"), nullable=True)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_centers.cost_center_id", name="fk_purchase_orders_cost_center"), nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id", name="fk_purchase_orders_source_warehouse"), nullable=True)
    supplier_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.contact_id"), nullable=True
    )
    supplier_contact_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    supplier_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=True
    )
    supplier_address_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    shipping_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=True
    )
    shipping_address_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    terms_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms_and_conditions_templates.terms_template_id"), nullable=True
    )
    purchase_tax_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_taxes_and_charges_templates.template_id"), nullable=True)
    tax_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shipping_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipping_rules.shipping_rule_id"), nullable=True
    )
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal("1.00000000")
    )
    target_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    taxes_and_charges: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    shipping_charge: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    calculation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")

    __table_args__ = (
        Index("idx_po_tenant_number", "tenant_id", "po_number", unique=True),
        Index("ix_purchase_order_tenant_material_request", "tenant_id", "material_request_id"),
        CheckConstraint("exchange_rate > 0", name="ck_purchase_order_exchange_rate_positive"),
        CheckConstraint("discount_amount >= 0", name="ck_purchase_order_discount_nonnegative"),
    )


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
    material_request_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_request_items.mr_item_id"), nullable=True
    )
    rfq_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfq_items.rfq_item_id"), nullable=True
    )
    supplier_quotation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_quotation_items.sq_item_id"), nullable=True
    )
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uoms.uom_id"), nullable=True
    )
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal("1.00000000")
    )
    stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    target_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.price_list_id"), nullable=True
    )
    item_price_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_prices.item_price_id"), nullable=True
    )
    price_list_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    pricing_rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pricing_rules.pricing_rule_id"), nullable=True)
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("promotional_schemes.scheme_id"), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    item = relationship("Item")

    __table_args__ = (
        Index("ix_purchase_order_item_tenant_mr_item", "tenant_id", "material_request_item_id"),
        Index("ix_purchase_order_item_tenant_sq_item", "tenant_id", "supplier_quotation_item_id"),
        CheckConstraint("conversion_factor > 0", name="ck_purchase_order_item_conversion_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_purchase_order_item_stock_quantity_nonnegative"),
        CheckConstraint("discount_amount >= 0", name="ck_purchase_order_item_discount_nonnegative"),
    )


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
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True)
    inspection_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quantity_accepted: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    quantity_rejected: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    rejected_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    material_request_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_request_items.mr_item_id"), nullable=True
    )
    supplier_quotation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_quotation_items.sq_item_id"), nullable=True
    )

    grn: Mapped["GoodsReceiptNote"] = relationship(back_populates="items")
    item = relationship("Item")
    rejected_warehouse = relationship("Warehouse", foreign_keys=[rejected_warehouse_id])
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])

    __table_args__ = (
        CheckConstraint("conversion_factor > 0", name="ck_grn_item_conversion_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_grn_item_stock_quantity_nonnegative"),
    )


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
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    purchase_tax_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_taxes_and_charges_templates.template_id"), nullable=True)
    tax_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
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
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    po_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_order_items.item_line_id"), nullable=True
    )
    grn_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipt_note_items.grn_item_id"), nullable=True
    )

    invoice: Mapped["SupplierInvoice"] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_supplier_invoice_item_tenant_po_item", "tenant_id", "po_item_id"),
        Index("ix_supplier_invoice_item_tenant_grn_item", "tenant_id", "grn_item_id"),
    )


class DocumentAuditBatch(Base, TenantMixin):
    """Idempotent audit container for lineage backfills and bulk document actions."""

    __tablename__ = "document_audit_batches"

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "operation", "idempotency_key", name="uq_document_audit_batch_idempotency"),
        CheckConstraint("status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name="ck_document_audit_batch_status"),
        Index("ix_document_audit_batch_tenant_operation", "tenant_id", "operation", "created_at"),
    )


# =========================================================================
# 1. Material Requests & Purchase Requisitions
# =========================================================================


class MaterialRequest(Base, TenantMixin, TimestampMixin):
    """Internal departmental or replenishment requisition."""

    __tablename__ = "material_requests"

    mr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mr_number: Mapped[str] = mapped_column(String(64), nullable=False)
    material_request_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PURCHASE"  # PURCHASE, MATERIAL_TRANSFER, MATERIAL_ISSUE, MANUFACTURE
    )
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, ORDERED, PARTIALLY_ORDERED, CANCELLED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terms_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms_and_conditions_templates.terms_template_id"), nullable=True
    )
    terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.project_id", name="fk_material_requests_project"), nullable=True)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_centers.cost_center_id", name="fk_material_requests_cost_center"), nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id", name="fk_material_requests_source_warehouse"), nullable=True)
    amended_from_mr_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("material_requests.mr_id", name="fk_material_requests_amended_from"), nullable=True)

    items: Mapped[list["MaterialRequestItem"]] = relationship(
        back_populates="material_request", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_mr_tenant_number", "tenant_id", "mr_number", unique=True),)


class MaterialRequestItem(Base, TenantMixin, TimestampMixin):
    """Line item in a material request."""

    __tablename__ = "material_request_items"

    mr_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_requests.mr_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ordered_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    target_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    uom: Mapped[str] = mapped_column(String(32), nullable=False, default="Nos")
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id", name="fk_material_request_item_uom"), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    source_mr_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("material_request_items.mr_item_id", name="fk_material_request_item_source"), nullable=True)

    material_request: Mapped["MaterialRequest"] = relationship(back_populates="items")
    item = relationship("Item")
    target_warehouse = relationship("Warehouse", foreign_keys=[target_warehouse_id])

    __table_args__ = (
        CheckConstraint("conversion_factor > 0", name="ck_mr_item_conversion_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_mr_item_stock_quantity_nonnegative"),
    )


# =========================================================================
# 2. Request for Quotation (RFQ)
# =========================================================================


class RequestForQuotation(Base, TenantMixin, TimestampMixin):
    """Request for Quotation sent to multiple competing suppliers."""

    __tablename__ = "request_for_quotations"

    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfq_number: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SENT, QUOTES_RECEIVED, COMPLETED, CANCELLED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["RFQItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    suppliers: Mapped[list["RFQSupplier"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_rfq_tenant_number", "tenant_id", "rfq_number", unique=True),)


class RFQItem(Base, TenantMixin, TimestampMixin):
    """Item requested in an RFQ."""

    __tablename__ = "rfq_items"

    rfq_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("request_for_quotations.rfq_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    rfq: Mapped["RequestForQuotation"] = relationship(back_populates="items")
    item = relationship("Item")


class RFQSupplier(Base, TenantMixin, TimestampMixin):
    """Supplier invited to tender a bid on an RFQ."""

    __tablename__ = "rfq_suppliers"

    rfq_supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("request_for_quotations.rfq_id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"  # PENDING, SUBMITTED, DECLINED
    )

    rfq: Mapped["RequestForQuotation"] = relationship(back_populates="suppliers")
    supplier = relationship("Supplier")


# =========================================================================
# 3. Supplier Quotations
# =========================================================================


class SupplierQuotation(Base, TenantMixin, TimestampMixin):
    """Vendor bid submission against an RFQ or standalone."""

    __tablename__ = "supplier_quotations"

    sq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quotation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("request_for_quotations.rfq_id"), nullable=True
    )
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    grand_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    payment_terms: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, AWARDED, REJECTED
    )

    items: Mapped[list["SupplierQuotationItem"]] = relationship(
        back_populates="supplier_quotation", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")
    rfq = relationship("RequestForQuotation")

    __table_args__ = (
        Index("idx_sq_tenant_number", "tenant_id", "supplier_id", "quotation_number", unique=True),
    )


class SupplierQuotationItem(Base, TenantMixin, TimestampMixin):
    """Line item in a supplier quotation."""

    __tablename__ = "supplier_quotation_items"

    sq_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_quotations.sq_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uoms.uom_id", name="fk_supplier_quotation_item_uom"), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1.00000000"))
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))

    supplier_quotation: Mapped["SupplierQuotation"] = relationship(back_populates="items")
    item = relationship("Item")


# =========================================================================
# 4. Blanket Orders (Long-Term Purchasing Contracts)
# =========================================================================


class BlanketOrder(Base, TenantMixin, TimestampMixin):
    """Long-term vendor purchasing agreement with agreed rates and drawdown tracking."""

    __tablename__ = "blanket_orders"

    blanket_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"  # DRAFT, ACTIVE, EXPIRED, CLOSED
    )

    items: Mapped[list["BlanketOrderItem"]] = relationship(
        back_populates="blanket_order", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")

    __table_args__ = (Index("idx_bo_tenant_number", "tenant_id", "order_number", unique=True),)


class BlanketOrderItem(Base, TenantMixin, TimestampMixin):
    """Itemized commitment in a blanket order."""

    __tablename__ = "blanket_order_items"

    bo_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    blanket_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blanket_orders.blanket_order_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ordered_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    blanket_order: Mapped["BlanketOrder"] = relationship(back_populates="items")
    item = relationship("Item")


# =========================================================================
# 5. Supplier Scorecard & Evaluation System
# =========================================================================


class SupplierScorecard(Base, TenantMixin, TimestampMixin):
    """Periodic supplier performance scorecard evaluating OTIF, Quality, and Pricing."""

    __tablename__ = "supplier_scorecards"

    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    evaluation_period: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MONTHLY"  # MONTHLY, QUARTERLY, ANNUAL
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    otif_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    quality_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    pricing_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    total_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    standing: Mapped[str] = mapped_column(
        String(32), nullable=False, default="STANDARD"  # PREFERRED, STANDARD, AT_RISK, BLACKLISTED
    )
    prevent_pos_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    criteria: Mapped[list["SupplierScorecardCriteria"]] = relationship(
        back_populates="scorecard", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")


class SupplierScorecardCriteria(Base, TenantMixin, TimestampMixin):
    """Individual KPI criteria evaluated on a supplier scorecard."""

    __tablename__ = "supplier_scorecard_criteria"

    criteria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_scorecards.scorecard_id"), nullable=False
    )
    criteria_name: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("33.33"))
    raw_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("100.00"))
    weighted_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("33.33"))

    scorecard: Mapped["SupplierScorecard"] = relationship(back_populates="criteria")
