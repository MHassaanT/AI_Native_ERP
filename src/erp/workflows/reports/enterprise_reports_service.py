"""Operational and commercial reports added in the enterprise reports sprint.

All queries are tenant scoped. These reports intentionally return aggregate rows
and small detail lists; they do not materialize whole ledgers in Python.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from erp.db.models.inventory import Item, StockLayerConsumption, StockLedgerEntry, StockLevel, StockValuationLayer, Warehouse
from erp.db.models.purchasing import (
    GoodsReceiptNote, GoodsReceiptNoteItem, MaterialRequest, MaterialRequestItem,
    PurchaseOrder, PurchaseOrderItem, Supplier, SupplierInvoice, SupplierInvoiceItem,
)
from erp.db.models.sales import (
    Customer, DeliveryNote, DeliveryNoteItem, SalesInvoice, SalesInvoiceItem,
    SalesOrder, SalesOrderItem, SalesQuotation,
)
from erp.db.models.phase_b import SalesPartner, SalesTeam
from erp.db.models.shared_master import UOM
from erp.db.models.support import Issue
from erp.db.models.hr import (
    Employee, EmployeeSeparation, LeaveAllocation, LeaveApplication, LeaveType,
)
from erp.db.models.recruitment import RecruitmentRole, CandidateApplication
from erp.db.models.hr_deep import Interview
from erp.db.models.subcontracting import (
    SubcontractingOrder, SubcontractingOrderItem, SubcontractingReceipt,
    SubcontractingReceiptItem, SubcontractingSuppliedItem,
)


class EnterpriseReportsService:
    """SQL backed reporting for the commercial, stock, HR and support domains."""

    @staticmethod
    def _period(model_date, from_date: date | None, to_date: date | None):
        filters = []
        if from_date:
            filters.append(model_date >= from_date)
        if to_date:
            filters.append(model_date <= to_date)
        return filters

    @staticmethod
    def _sales_order_line_progress(line: SalesOrderItem, order_status: str) -> dict[str, Decimal]:
        """Calculate outstanding quantities and values from persisted line counters."""
        ordered = Decimal(line.quantity)
        delivered = Decimal(line.delivered_quantity)
        invoiced = Decimal(line.invoiced_quantity)
        returned = Decimal(line.returned_quantity)
        line_total = Decimal(line.line_total)
        pending_delivery = Decimal("0") if order_status == "CANCELLED" else max(Decimal("0"), ordered - delivered)
        pending_billing = Decimal("0") if order_status == "CANCELLED" else max(Decimal("0"), delivered - invoiced)
        divisor = ordered if ordered > 0 else Decimal("1")
        return {
            "ordered_quantity": ordered,
            "delivered_quantity": delivered,
            "invoiced_quantity": invoiced,
            "returned_quantity": returned,
            "pending_delivery_quantity": pending_delivery,
            "pending_billing_quantity": pending_billing,
            "pending_delivery_amount": (line_total * pending_delivery / divisor).quantize(Decimal("0.0001")),
            "pending_billing_amount": (line_total * pending_billing / divisor).quantize(Decimal("0.0001")),
        }

    async def run(self, name: str, db: AsyncSession, tenant_id: uuid.UUID,
                  from_date: date | None = None, to_date: date | None = None,
                  as_of_date: date | None = None, month: int | None = None,
                  fiscal_year: int | None = None, item_id: uuid.UUID | None = None,
                  party_id: uuid.UUID | None = None, currency: str | None = None,
                  territory: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        as_of_date = as_of_date or to_date or date.today()
        period = (from_date, to_date)

        if name == "item-wise-purchase-history":
            receipts = select(
                GoodsReceiptNoteItem.po_item_id.label("po_item_id"),
                func.sum(GoodsReceiptNoteItem.quantity_accepted).label("accepted_qty"),
                func.sum(GoodsReceiptNoteItem.quantity_rejected).label("rejected_qty"),
                func.string_agg(func.distinct(GoodsReceiptNote.grn_number), ", ").label("receipt_numbers"),
            ).join(GoodsReceiptNote, GoodsReceiptNote.grn_id == GoodsReceiptNoteItem.grn_id).where(
                GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNoteItem.tenant_id == tenant_id,
                GoodsReceiptNote.status != "CANCELLED", GoodsReceiptNoteItem.po_item_id.is_not(None),
            ).group_by(GoodsReceiptNoteItem.po_item_id).subquery()
            invoices = select(
                SupplierInvoiceItem.po_item_id.label("po_item_id"),
                func.sum(SupplierInvoiceItem.quantity).label("invoiced_qty"),
                func.sum(SupplierInvoiceItem.line_total).label("invoiced_amount"),
                func.string_agg(func.distinct(SupplierInvoice.invoice_number), ", ").label("invoice_numbers"),
            ).join(SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id).where(
                SupplierInvoice.tenant_id == tenant_id, SupplierInvoiceItem.tenant_id == tenant_id,
                SupplierInvoice.matching_status != "CANCELLED", SupplierInvoiceItem.po_item_id.is_not(None),
            ).group_by(SupplierInvoiceItem.po_item_id).subquery()
            stmt = select(
                PurchaseOrder.po_id, PurchaseOrder.po_number, PurchaseOrder.order_date,
                PurchaseOrder.currency, PurchaseOrder.status, Supplier.supplier_id, Supplier.supplier_name,
                Item.item_id, Item.item_code, Item.item_name, PurchaseOrderItem.item_line_id,
                PurchaseOrderItem.quantity, PurchaseOrderItem.stock_quantity, PurchaseOrderItem.unit_price,
                PurchaseOrderItem.price_list_rate, PurchaseOrderItem.discount_amount,
                UOM.uom_name, PurchaseOrderItem.conversion_factor,
                func.coalesce(receipts.c.accepted_qty, 0).label("accepted_qty"),
                func.coalesce(receipts.c.rejected_qty, 0).label("rejected_qty"), receipts.c.receipt_numbers,
                func.coalesce(invoices.c.invoiced_qty, 0).label("invoiced_qty"),
                func.coalesce(invoices.c.invoiced_amount, 0).label("invoiced_amount"), invoices.c.invoice_numbers,
            ).join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id)\
             .join(Supplier, Supplier.supplier_id == PurchaseOrder.supplier_id)\
             .join(Item, Item.item_id == PurchaseOrderItem.item_id)\
             .outerjoin(UOM, (UOM.uom_id == PurchaseOrderItem.uom_id) & (UOM.tenant_id == tenant_id))\
             .outerjoin(receipts, receipts.c.po_item_id == PurchaseOrderItem.item_line_id)\
             .outerjoin(invoices, invoices.c.po_item_id == PurchaseOrderItem.item_line_id)\
             .where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrderItem.tenant_id == tenant_id,
                    Supplier.tenant_id == tenant_id, Item.tenant_id == tenant_id,
                    PurchaseOrder.status != "CANCELLED", *self._period(PurchaseOrder.order_date, *period))
            if item_id:
                stmt = stmt.where(Item.item_id == item_id)
            if party_id:
                stmt = stmt.where(Supplier.supplier_id == party_id)
            if currency:
                stmt = stmt.where(PurchaseOrder.currency == currency.upper())
            rows = (await db.execute(stmt.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.po_number))).all()
            return {"report_name": "Item-wise Purchase History",
                    "tax_note": "Tax and landed cost are not available per PO line in legacy records; linked invoice totals are shown before tax.",
                    "rows": [{"po_id": str(r.po_id), "po_number": r.po_number, "po_item_id": str(r.item_line_id),
                              "date": r.order_date.isoformat(), "status": r.status, "currency": r.currency,
                              "supplier_id": str(r.supplier_id), "supplier": r.supplier_name,
                              "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name,
                              "quantity": r.quantity, "purchase_uom": r.uom_name or "Stock UOM",
                              "conversion_factor": r.conversion_factor, "stock_quantity": r.stock_quantity,
                              "rate": r.unit_price, "price_list_rate": r.price_list_rate,
                              "discount_amount": r.discount_amount, "accepted_quantity": r.accepted_qty,
                              "rejected_quantity": r.rejected_qty, "receipt_numbers": r.receipt_numbers,
                              "invoiced_quantity": r.invoiced_qty, "invoiced_amount_before_tax": r.invoiced_amount,
                              "invoice_numbers": r.invoice_numbers} for r in rows]}

        if name == "item-wise-sales-history":
            sales_territories = select(
                SalesTeam.document_id.label("invoice_id"),
                func.string_agg(func.distinct(SalesPartner.territory), ", ").label("territories"),
            ).join(SalesPartner, (SalesPartner.sales_partner_id == SalesTeam.sales_partner_id) &
                                  (SalesPartner.tenant_id == tenant_id)).where(
                SalesTeam.tenant_id == tenant_id,
                SalesTeam.document_type.in_(("Sales Invoice", "SALES_INVOICE")),
            ).group_by(SalesTeam.document_id).subquery()
            stmt = select(
                SalesInvoice.invoice_id, SalesInvoice.invoice_number, SalesInvoice.invoice_date,
                SalesInvoice.currency, SalesInvoice.status, Customer.customer_id, Customer.customer_name,
                sales_territories.c.territories, Item.item_id, Item.item_code, Item.item_name, SalesInvoiceItem.invoice_item_id,
                SalesInvoiceItem.quantity, SalesInvoiceItem.unit_price, SalesInvoiceItem.line_total,
                SalesInvoiceItem.discount_amount, SalesOrderItem.uom_id, UOM.uom_name,
                SalesOrderItem.conversion_factor,
                SalesOrderItem.stock_quantity, SalesOrderItem.price_list_rate, SalesOrder.order_id,
                SalesOrder.order_number, DeliveryNote.delivery_note_id, DeliveryNote.delivery_note_number,
                DeliveryNoteItem.quantity.label("delivered_quantity"), SalesInvoice.tax_amount.label("invoice_tax_amount"),
            ).join(SalesInvoiceItem, (SalesInvoiceItem.invoice_id == SalesInvoice.invoice_id) & (SalesInvoiceItem.tenant_id == tenant_id))\
             .join(Customer, Customer.customer_id == SalesInvoice.customer_id)\
             .join(Item, Item.item_id == SalesInvoiceItem.item_id)\
             .outerjoin(sales_territories, sales_territories.c.invoice_id == SalesInvoice.invoice_id)\
             .outerjoin(SalesOrderItem, (SalesOrderItem.order_item_id == SalesInvoiceItem.order_item_id) & (SalesOrderItem.tenant_id == tenant_id))\
             .outerjoin(UOM, (UOM.uom_id == SalesOrderItem.uom_id) & (UOM.tenant_id == tenant_id))\
             .outerjoin(SalesOrder, (SalesOrder.order_id == SalesOrderItem.order_id) & (SalesOrder.tenant_id == tenant_id))\
             .outerjoin(DeliveryNoteItem, (DeliveryNoteItem.dn_item_id == SalesInvoiceItem.delivery_note_item_id) & (DeliveryNoteItem.tenant_id == tenant_id))\
             .outerjoin(DeliveryNote, (DeliveryNote.delivery_note_id == DeliveryNoteItem.delivery_note_id) & (DeliveryNote.tenant_id == tenant_id))\
             .where(SalesInvoice.tenant_id == tenant_id, Customer.tenant_id == tenant_id,
                    Item.tenant_id == tenant_id, SalesInvoice.status != "CANCELLED",
                    *self._period(SalesInvoice.invoice_date, *period))
            if item_id:
                stmt = stmt.where(Item.item_id == item_id)
            if party_id:
                stmt = stmt.where(Customer.customer_id == party_id)
            if currency:
                stmt = stmt.where(SalesInvoice.currency == currency.upper())
            if territory:
                stmt = stmt.where(sales_territories.c.territories.ilike(f"%{territory}%"))
            rows = (await db.execute(stmt.order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.invoice_number))).all()
            return {"report_name": "Item-wise Sales History", "margin_snapshot_available": False,
                    "tax_note": "Tax is stored at invoice level; no line-level allocation is inferred.",
                    "territory_basis": "Territories are sales-partner assignments on the invoice; customer territory is not modeled.",
                    "rows": [{"invoice_id": str(r.invoice_id), "invoice_number": r.invoice_number,
                              "invoice_item_id": str(r.invoice_item_id), "date": r.invoice_date.isoformat(),
                              "status": r.status, "currency": r.currency, "customer_id": str(r.customer_id),
                              "customer": r.customer_name, "sales_partner_territories": r.territories,
                              "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name,
                              "quantity": r.quantity, "sales_uom": r.uom_name or "Stock UOM",
                              "sales_uom_id": str(r.uom_id) if r.uom_id else None,
                              "conversion_factor": r.conversion_factor or Decimal("1"),
                              "stock_quantity": r.stock_quantity or r.quantity,
                              "unit_price": r.unit_price, "price_list_rate": r.price_list_rate,
                              "discount_amount": r.discount_amount, "line_total": r.line_total,
                              "invoice_tax_amount_unallocated": r.invoice_tax_amount,
                              "sales_order_id": str(r.order_id) if r.order_id else None,
                              "sales_order_number": r.order_number,
                              "delivery_note_id": str(r.delivery_note_id) if r.delivery_note_id else None,
                              "delivery_note_number": r.delivery_note_number,
                              "delivered_quantity": r.delivered_quantity} for r in rows]}

        if name in {"customer-ledger-summary", "supplier-ledger-summary"}:
            if name.startswith("customer"):
                entity, inv, date_col, id_col, label = Customer, SalesInvoice, SalesInvoice.invoice_date, SalesInvoice.customer_id, "customer"
                amount = SalesInvoice.total_amount
                join_cond = SalesInvoice.customer_id == Customer.customer_id
                status_col = SalesInvoice.status
                paid_values = ("PAID",)
            else:
                entity, inv, date_col, id_col, label = Supplier, SupplierInvoice, SupplierInvoice.invoice_date, SupplierInvoice.supplier_id, "supplier"
                amount = SupplierInvoice.total_amount
                join_cond = SupplierInvoice.supplier_id == Supplier.supplier_id
                status_col = SupplierInvoice.matching_status
                paid_values = ("POSTED", "MATCHED")
            stmt = select(entity, func.count(inv.invoice_id), func.coalesce(func.sum(amount), 0),
                          func.coalesce(func.sum(case((status_col.in_(paid_values), amount), else_=0)), 0)).join(inv, join_cond).where(entity.tenant_id == tenant_id, inv.tenant_id == tenant_id, *self._period(date_col, *period)).group_by(entity).order_by(func.sum(amount).desc())
            rows = (await db.execute(stmt)).all()
            return [{"id": str(e.customer_id if label == "customer" else e.supplier_id), "name": e.customer_name if label == "customer" else e.supplier_name,
                     "invoice_count": int(n), "invoiced": total, "settled_or_posted": settled, "open_balance_estimate": total - settled} for e, n, total, settled in rows]

        if name == "gross-profit-analysis":
            # Historical line-level COGS is not stored on invoice lines. Use the
            # outbound stock ledger rate for linked delivery notes; otherwise use
            # current item standard_rate and flag the estimate in the payload.
            delivery_cost = select(
                StockLedgerEntry.source_document_id.label("delivery_note_id"),
                StockLedgerEntry.item_id.label("item_id"),
                (func.sum(StockLedgerEntry.actual_qty * StockLedgerEntry.outgoing_rate)
                 / func.nullif(func.sum(StockLedgerEntry.actual_qty), 0)).label("weighted_rate"),
            ).where(
                StockLedgerEntry.tenant_id == tenant_id,
                StockLedgerEntry.source_document_type == "DELIVERY_NOTE",
                StockLedgerEntry.actual_qty < 0,
                StockLedgerEntry.is_cancelled.is_(False),
            ).group_by(StockLedgerEntry.source_document_id, StockLedgerEntry.item_id).subquery()
            cost = func.coalesce(delivery_cost.c.weighted_rate, Item.standard_rate, 0)
            stmt = select(Item.item_id, Item.item_code, Item.item_name, Customer.customer_id,
                          Customer.customer_name, func.sum(SalesInvoiceItem.line_total).label("revenue"),
                          func.sum(SalesInvoiceItem.quantity * cost).label("estimated_cost"))\
                .join(SalesInvoice, SalesInvoice.invoice_id == SalesInvoiceItem.invoice_id)\
                .join(Customer, Customer.customer_id == SalesInvoice.customer_id)\
                .join(Item, Item.item_id == SalesInvoiceItem.item_id)\
                .outerjoin(DeliveryNote, DeliveryNote.delivery_note_id == SalesInvoice.delivery_note_id)\
                .outerjoin(delivery_cost, (delivery_cost.c.delivery_note_id == DeliveryNote.delivery_note_id) & (delivery_cost.c.item_id == Item.item_id))\
                .where(SalesInvoice.tenant_id == tenant_id, SalesInvoiceItem.tenant_id == tenant_id, Item.tenant_id == tenant_id, Customer.tenant_id == tenant_id, SalesInvoice.status != "CANCELLED", *self._period(SalesInvoice.invoice_date, *period))\
                .group_by(Item.item_id, Item.item_code, Item.item_name, Customer.customer_id, Customer.customer_name)
            rows = (await db.execute(stmt)).all()
            data = [{"item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name,
                     "customer_id": str(r.customer_id), "customer_name": r.customer_name,
                     "revenue": r.revenue or 0, "estimated_cost": r.estimated_cost or 0,
                     "gross_profit_estimate": (r.revenue or 0) - (r.estimated_cost or 0)} for r in rows]
            return {"cost_basis": "Delivery Note stock ledger outgoing rate; falls back to current item standard rate", "historical_cost_is_estimated": True, "rows": data}

        trend_sources = {
            "sales-invoice-trends": (SalesInvoice, SalesInvoice.invoice_date, SalesInvoice.total_amount, SalesInvoice.status, "invoice"),
            "purchase-invoice-trends": (SupplierInvoice, SupplierInvoice.invoice_date, SupplierInvoice.total_amount, SupplierInvoice.matching_status, "invoice"),
            "quotation-trends": (SalesQuotation, SalesQuotation.quotation_date, SalesQuotation.total_amount, SalesQuotation.status, "quotation"),
            "sales-order-trends": (SalesOrder, SalesOrder.order_date, SalesOrder.total_amount, SalesOrder.status, "order"),
            "delivery-note-trends": (DeliveryNote, DeliveryNote.delivery_date, DeliveryNote.delivery_note_id, DeliveryNote.status, "delivery"),
        }
        if name in trend_sources:
            model, date_col, amount_col, status_col, kind = trend_sources[name]
            bucket = func.date_trunc("month", date_col)
            measures = [func.count().label("document_count")]
            if kind != "delivery": measures.append(func.coalesce(func.sum(amount_col), 0).label("amount"))
            stmt = select(bucket.label("period"), status_col, *measures).where(model.tenant_id == tenant_id, *self._period(date_col, *period)).group_by(bucket, status_col).order_by(bucket)
            rows = (await db.execute(stmt)).all()
            return [{"period": r.period.date().isoformat() if hasattr(r.period, "date") else str(r.period), "status": r.status,
                     "document_count": int(r.document_count), **({"amount": r.amount} if kind != "delivery" else {})} for r in rows]

        if name in {"purchase-analytics", "supplier-wise-sales-analytics"}:
            purchase_month = func.date_trunc("month", PurchaseOrder.order_date)
            stmt = select(purchase_month.label("period"), Supplier.supplier_id, Supplier.supplier_name, Item.item_id, Item.item_code, Item.item_name,
                          func.sum(PurchaseOrderItem.quantity).label("quantity"), func.sum(PurchaseOrderItem.line_total).label("amount"))\
                .join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id)\
                .join(Supplier, Supplier.supplier_id == PurchaseOrder.supplier_id)\
                .join(Item, Item.item_id == PurchaseOrderItem.item_id)\
                .where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrderItem.tenant_id == tenant_id,
                       Supplier.tenant_id == tenant_id, Item.tenant_id == tenant_id, *self._period(PurchaseOrder.order_date, *period))\
                .group_by(purchase_month, Supplier.supplier_id, Supplier.supplier_name, Item.item_id, Item.item_code, Item.item_name).order_by(purchase_month, func.sum(PurchaseOrderItem.line_total).desc())
            rows = (await db.execute(stmt)).all()
            # Keep the legacy endpoint as an alias, but never mislabel buying as sales.
            return {"report_name": "Supplier Sourcing Analysis", "attribution_note": "Sales are not linked to suppliers in the current schema; rows show supplier-sourced purchase activity by item, not supplier-attributed revenue.",
                    "rows": [{"period": r.period.date().isoformat(), "supplier_id": str(r.supplier_id), "supplier_name": r.supplier_name, "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name, "quantity": r.quantity, "purchase_amount": r.amount} for r in rows]}

        if name == "purchase-order-analytics":
            overdue_cutoff = as_of_date - timedelta(days=30)
            stmt = select(PurchaseOrder.po_id, PurchaseOrder.po_number, Supplier.supplier_name, PurchaseOrder.order_date, PurchaseOrder.status, PurchaseOrder.total_amount, (PurchaseOrder.order_date < overdue_cutoff).label("overdue"))\
                .join(Supplier, Supplier.supplier_id == PurchaseOrder.supplier_id).where(PurchaseOrder.tenant_id == tenant_id, Supplier.tenant_id == tenant_id, *self._period(PurchaseOrder.order_date, *period)).order_by(PurchaseOrder.order_date)
            return [{"po_id": str(r.po_id), "po_number": r.po_number, "supplier": r.supplier_name, "order_date": r.order_date, "status": r.status, "total_amount": r.total_amount, "overdue_after_days": 30, "overdue": bool(r.overdue and r.status not in ("COMPLETED", "CANCELLED"))} for r in (await db.execute(stmt)).all()]

        if name == "subcontracting-materials":
            source_warehouse = aliased(Warehouse)
            supplier_warehouse = aliased(Warehouse)
            first_transfer = select(
                StockLedgerEntry.source_document_id.label("sco_id"),
                StockLedgerEntry.item_id.label("item_id"),
                StockLedgerEntry.warehouse_id.label("warehouse_id"),
                func.min(StockLedgerEntry.posting_datetime).label("first_transferred_at"),
            ).where(
                StockLedgerEntry.tenant_id == tenant_id,
                StockLedgerEntry.source_document_type == "SUBCONTRACTING_TRANSFER_IN",
                StockLedgerEntry.is_cancelled.is_(False),
            ).group_by(
                StockLedgerEntry.source_document_id, StockLedgerEntry.item_id, StockLedgerEntry.warehouse_id,
            ).subquery()
            stmt = select(
                SubcontractingOrder.sco_id, SubcontractingOrder.sco_number,
                SubcontractingOrder.order_date, SubcontractingOrder.status,
                Supplier.supplier_id, Supplier.supplier_name,
                SubcontractingSuppliedItem.supplied_item_id, Item.item_id,
                Item.item_code, Item.item_name, SubcontractingSuppliedItem.required_qty,
                SubcontractingSuppliedItem.supplied_qty, SubcontractingSuppliedItem.consumed_qty,
                SubcontractingSuppliedItem.source_warehouse_id,
                source_warehouse.warehouse_name.label("source_warehouse_name"),
                SubcontractingSuppliedItem.supplier_warehouse_id,
                supplier_warehouse.warehouse_name.label("supplier_warehouse_name"),
                first_transfer.c.first_transferred_at,
            ).join(SubcontractingOrder, (SubcontractingOrder.sco_id == SubcontractingSuppliedItem.sco_id) &
                   (SubcontractingOrder.tenant_id == tenant_id))\
             .join(Supplier, (Supplier.supplier_id == SubcontractingOrder.supplier_id) &
                   (Supplier.tenant_id == tenant_id))\
             .join(Item, (Item.item_id == SubcontractingSuppliedItem.raw_item_id) &
                   (Item.tenant_id == tenant_id))\
             .outerjoin(source_warehouse, (source_warehouse.warehouse_id == SubcontractingSuppliedItem.source_warehouse_id) &
                        (source_warehouse.tenant_id == tenant_id))\
             .outerjoin(supplier_warehouse, (supplier_warehouse.warehouse_id == SubcontractingSuppliedItem.supplier_warehouse_id) &
                        (supplier_warehouse.tenant_id == tenant_id))\
             .outerjoin(first_transfer, (first_transfer.c.sco_id == SubcontractingOrder.sco_id) &
                        (first_transfer.c.item_id == SubcontractingSuppliedItem.raw_item_id) &
                        (first_transfer.c.warehouse_id == SubcontractingSuppliedItem.supplier_warehouse_id))\
             .where(SubcontractingSuppliedItem.tenant_id == tenant_id,
                    *self._period(SubcontractingOrder.order_date, *period))\
             .order_by(SubcontractingOrder.order_date, SubcontractingOrder.sco_number, Item.item_code)
            rows = (await db.execute(stmt)).all()
            return {"report_name": "Subcontracted Raw Material Tracker", "rows": [{
                "sco_id": str(r.sco_id), "sco_number": r.sco_number, "status": r.status,
                "order_date": r.order_date.isoformat(), "supplier_id": str(r.supplier_id),
                "supplier": r.supplier_name, "supplied_item_id": str(r.supplied_item_id),
                "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name,
                "required_quantity": r.required_qty, "supplied_quantity": r.supplied_qty,
                "consumed_quantity": r.consumed_qty,
                "short_to_supply": max(Decimal("0"), r.required_qty - r.supplied_qty),
                "currently_at_subcontractor": max(Decimal("0"), r.supplied_qty - r.consumed_qty),
                "source_warehouse_id": str(r.source_warehouse_id) if r.source_warehouse_id else None,
                "source_warehouse": r.source_warehouse_name,
                "supplier_warehouse_id": str(r.supplier_warehouse_id) if r.supplier_warehouse_id else None,
                "supplier_warehouse": r.supplier_warehouse_name,
                "first_transfer_at": r.first_transferred_at.isoformat() if r.first_transferred_at else None,
                "days_since_first_transfer": (as_of_date - r.first_transferred_at.date()).days if r.first_transferred_at else None,
                "lineage_basis": "Explicit subcontracting order, supplied-item, and transfer stock-ledger references.",
            } for r in rows]}

        if name == "subcontracting-finished-goods":
            receipts = select(
                SubcontractingReceipt.sco_id.label("sco_id"),
                SubcontractingReceiptItem.item_id.label("item_id"),
                func.sum(SubcontractingReceiptItem.quantity_received).label("received_qty"),
                func.string_agg(func.distinct(SubcontractingReceipt.scr_number), ", ").label("receipt_numbers"),
            ).join(SubcontractingReceiptItem, (SubcontractingReceiptItem.scr_id == SubcontractingReceipt.scr_id) &
                   (SubcontractingReceiptItem.tenant_id == tenant_id)).where(
                SubcontractingReceipt.tenant_id == tenant_id,
                SubcontractingReceipt.status != "CANCELLED",
            ).group_by(SubcontractingReceipt.sco_id, SubcontractingReceiptItem.item_id).subquery()
            stmt = select(
                SubcontractingOrder.sco_id, SubcontractingOrder.sco_number,
                SubcontractingOrder.order_date, SubcontractingOrder.status,
                Supplier.supplier_id, Supplier.supplier_name,
                SubcontractingOrderItem.sco_item_id, Item.item_id, Item.item_code, Item.item_name,
                SubcontractingOrderItem.quantity.label("ordered_qty"),
                func.coalesce(receipts.c.received_qty, 0).label("received_qty"),
                receipts.c.receipt_numbers,
            ).join(SubcontractingOrder, (SubcontractingOrder.sco_id == SubcontractingOrderItem.sco_id) &
                   (SubcontractingOrder.tenant_id == tenant_id))\
             .join(Supplier, (Supplier.supplier_id == SubcontractingOrder.supplier_id) &
                   (Supplier.tenant_id == tenant_id))\
             .join(Item, (Item.item_id == SubcontractingOrderItem.item_id) & (Item.tenant_id == tenant_id))\
             .outerjoin(receipts, (receipts.c.sco_id == SubcontractingOrder.sco_id) &
                        (receipts.c.item_id == SubcontractingOrderItem.item_id))\
             .where(SubcontractingOrderItem.tenant_id == tenant_id,
                    *self._period(SubcontractingOrder.order_date, *period))\
             .order_by(SubcontractingOrder.order_date, SubcontractingOrder.sco_number, Item.item_code)
            rows = (await db.execute(stmt)).all()
            return {"report_name": "Subcontracting Finished Goods Receipt Tracker", "rows": [{
                "sco_id": str(r.sco_id), "sco_number": r.sco_number, "status": r.status,
                "order_date": r.order_date.isoformat(), "supplier_id": str(r.supplier_id),
                "supplier": r.supplier_name, "sco_item_id": str(r.sco_item_id),
                "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name,
                "ordered_quantity": r.ordered_qty, "received_quantity": r.received_qty,
                "pending_receipt_quantity": max(Decimal("0"), r.ordered_qty - r.received_qty),
                "over_received_quantity": max(Decimal("0"), r.received_qty - r.ordered_qty),
                "receipt_numbers": r.receipt_numbers,
                "lineage_basis": "Subcontracting receipt headers link directly to their subcontracting order.",
            } for r in rows]}

        if name == "procurement-tracker":
            receipts = select(
                GoodsReceiptNoteItem.po_item_id.label("po_item_id"),
                func.coalesce(func.sum(GoodsReceiptNoteItem.quantity_accepted), 0).label("accepted_qty"),
                func.coalesce(func.sum(GoodsReceiptNoteItem.quantity_rejected), 0).label("rejected_qty"),
                func.count(func.distinct(GoodsReceiptNoteItem.grn_id)).label("receipt_count"),
            ).join(GoodsReceiptNote, GoodsReceiptNote.grn_id == GoodsReceiptNoteItem.grn_id).where(
                GoodsReceiptNoteItem.tenant_id == tenant_id,
                GoodsReceiptNote.tenant_id == tenant_id,
                GoodsReceiptNote.status != "CANCELLED",
                GoodsReceiptNoteItem.po_item_id.is_not(None),
            ).group_by(GoodsReceiptNoteItem.po_item_id).subquery()
            invoices = select(
                SupplierInvoiceItem.po_item_id.label("po_item_id"),
                func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0).label("invoiced_qty"),
                func.coalesce(func.sum(SupplierInvoiceItem.line_total), 0).label("invoiced_amount"),
            ).join(SupplierInvoice, SupplierInvoice.invoice_id == SupplierInvoiceItem.invoice_id).where(
                SupplierInvoiceItem.tenant_id == tenant_id,
                SupplierInvoice.tenant_id == tenant_id,
                SupplierInvoice.matching_status != "CANCELLED",
                SupplierInvoiceItem.po_item_id.is_not(None),
            ).group_by(SupplierInvoiceItem.po_item_id).subquery()
            stmt = select(
                MaterialRequest.mr_id, MaterialRequest.mr_number, MaterialRequest.schedule_date, MaterialRequest.status,
                MaterialRequestItem.mr_item_id, Item.item_code, Item.item_name, MaterialRequestItem.quantity,
                MaterialRequestItem.ordered_qty, PurchaseOrder.po_id, PurchaseOrder.po_number, PurchaseOrder.status.label("po_status"),
                PurchaseOrderItem.item_line_id, PurchaseOrderItem.quantity.label("po_qty"),
                PurchaseOrderItem.stock_quantity.label("po_stock_qty"), PurchaseOrderItem.rfq_item_id,
                PurchaseOrderItem.supplier_quotation_item_id,
                func.coalesce(receipts.c.accepted_qty, 0).label("accepted_qty"),
                func.coalesce(receipts.c.rejected_qty, 0).label("rejected_qty"),
                func.coalesce(receipts.c.receipt_count, 0).label("receipt_count"),
                func.coalesce(invoices.c.invoiced_qty, 0).label("invoiced_qty"),
                func.coalesce(invoices.c.invoiced_amount, 0).label("invoiced_amount"),
            ).join(MaterialRequestItem, (MaterialRequestItem.mr_id == MaterialRequest.mr_id) & (MaterialRequestItem.tenant_id == tenant_id))\
             .join(Item, (Item.item_id == MaterialRequestItem.item_id) & (Item.tenant_id == tenant_id))\
             .outerjoin(PurchaseOrderItem, (PurchaseOrderItem.material_request_item_id == MaterialRequestItem.mr_item_id) & (PurchaseOrderItem.tenant_id == tenant_id))\
             .outerjoin(PurchaseOrder, (PurchaseOrder.po_id == PurchaseOrderItem.po_id) & (PurchaseOrder.tenant_id == tenant_id))\
             .outerjoin(receipts, receipts.c.po_item_id == PurchaseOrderItem.item_line_id)\
             .outerjoin(invoices, invoices.c.po_item_id == PurchaseOrderItem.item_line_id)\
             .where(MaterialRequest.tenant_id == tenant_id, *self._period(MaterialRequest.schedule_date, *period))\
             .order_by(MaterialRequest.schedule_date, MaterialRequestItem.mr_item_id, PurchaseOrder.po_number)
            rows = (await db.execute(stmt)).all()
            return [{
                "mr_id": str(r.mr_id), "mr_number": r.mr_number, "mr_item_id": str(r.mr_item_id),
                "schedule_date": r.schedule_date, "status": r.status, "item_code": r.item_code,
                "item_name": r.item_name, "requested_qty": r.quantity, "ordered_qty": r.ordered_qty,
                "remaining_to_order": max(Decimal("0"), r.quantity - r.ordered_qty),
                "po_id": str(r.po_id) if r.po_id else None, "po_number": r.po_number,
                "po_status": r.po_status, "po_item_id": str(r.item_line_id) if r.item_line_id else None,
                "po_qty": r.po_qty, "po_stock_qty": r.po_stock_qty,
                "rfq_item_id": str(r.rfq_item_id) if r.rfq_item_id else None,
                "supplier_quotation_item_id": str(r.supplier_quotation_item_id) if r.supplier_quotation_item_id else None,
                "accepted_qty": r.accepted_qty, "rejected_qty": r.rejected_qty,
                "receipt_count": r.receipt_count, "invoiced_qty": r.invoiced_qty,
                "invoiced_amount": r.invoiced_amount,
            } for r in rows]

        if name in {"items-to-be-requested", "item-shortage-report"}:
            stmt = select(Item.item_id, Item.item_code, Item.item_name, Item.reorder_level, func.coalesce(func.sum(StockLevel.current_qty), 0).label("on_hand"), func.coalesce(func.sum(StockLevel.reserved_qty), 0).label("reserved"))\
                .outerjoin(StockLevel, (StockLevel.item_id == Item.item_id) & (StockLevel.tenant_id == tenant_id) & (StockLevel.is_quarantined.is_(False)))\
                .where(Item.tenant_id == tenant_id, Item.is_active.is_(True)).group_by(Item.item_id, Item.item_code, Item.item_name, Item.reorder_level).having(func.coalesce(func.sum(StockLevel.available_qty), 0) < Item.reorder_level).order_by((Item.reorder_level - func.coalesce(func.sum(StockLevel.available_qty), 0)).desc())
            rows = (await db.execute(stmt)).all()
            return [{"item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name, "reorder_level": r.reorder_level, "on_hand": r.on_hand, "reserved": r.reserved, "shortage_qty": max(Decimal("0"), r.reorder_level - (r.on_hand - r.reserved))} for r in rows]

        if name == "sales-analytics":
            stmt = select(Customer.customer_id, Customer.customer_name, SalesInvoiceItem.item_id, Item.item_code, Item.item_name,
                          SalesPartner.territory, func.sum(SalesInvoiceItem.quantity).label("quantity"), func.sum(SalesInvoiceItem.line_total).label("revenue"))\
                .join(SalesInvoice, SalesInvoice.invoice_id == SalesInvoiceItem.invoice_id).join(Customer, Customer.customer_id == SalesInvoice.customer_id)\
                .join(Item, Item.item_id == SalesInvoiceItem.item_id).outerjoin(SalesTeam, (SalesTeam.document_id == SalesInvoice.invoice_id) & (SalesTeam.document_type.in_(("Sales Invoice", "SALES_INVOICE"))) & (SalesTeam.tenant_id == tenant_id))\
                .outerjoin(SalesPartner, (SalesPartner.sales_partner_id == SalesTeam.sales_partner_id) & (SalesPartner.tenant_id == tenant_id))\
                .where(SalesInvoice.tenant_id == tenant_id, SalesInvoiceItem.tenant_id == tenant_id, Customer.tenant_id == tenant_id, Item.tenant_id == tenant_id, SalesInvoice.status != "CANCELLED", *self._period(SalesInvoice.invoice_date, *period))\
                .group_by(Customer.customer_id, Customer.customer_name, SalesInvoiceItem.item_id, Item.item_code, Item.item_name, SalesPartner.territory).order_by(func.sum(SalesInvoiceItem.line_total).desc())
            rows = (await db.execute(stmt)).all()
            return [{"customer_id": str(r.customer_id), "customer_name": r.customer_name, "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name, "territory": r.territory or "Unassigned", "quantity": r.quantity, "revenue": r.revenue} for r in rows]

        if name == "sales-order-analysis":
            rows = (await db.execute(
                select(SalesOrder, Customer.customer_name, SalesOrderItem, Item.item_code, Item.item_name,
                       UOM.uom_name, SalesQuotation.currency)
                .join(Customer, (Customer.customer_id == SalesOrder.customer_id) & (Customer.tenant_id == tenant_id))
                .join(SalesOrderItem, (SalesOrderItem.order_id == SalesOrder.order_id) & (SalesOrderItem.tenant_id == tenant_id))
                .join(Item, (Item.item_id == SalesOrderItem.item_id) & (Item.tenant_id == tenant_id))
                .outerjoin(UOM, (UOM.uom_id == SalesOrderItem.uom_id) & (UOM.tenant_id == tenant_id))
                .outerjoin(SalesQuotation, (SalesQuotation.quotation_id == SalesOrder.source_quotation_id) &
                           (SalesQuotation.tenant_id == tenant_id))
                .where(SalesOrder.tenant_id == tenant_id, *self._period(SalesOrder.order_date, *period))
                .order_by(SalesOrder.order_date, SalesOrder.order_number, SalesOrderItem.order_item_id)
            )).all()
            result = []
            for order, customer, line, item_code, item_name, uom_name, currency_code in rows:
                progress = self._sales_order_line_progress(line, order.status)
                result.append({
                    "order_id": str(order.order_id), "order_number": order.order_number,
                    "order_item_id": str(line.order_item_id), "customer": customer,
                    "status": order.status, "order_date": order.order_date.isoformat(),
                    "delivery_date": order.delivery_date.isoformat(), "currency": currency_code,
                    "item_id": str(line.item_id), "item_code": item_code, "item_name": item_name,
                    "uom": uom_name or "Stock UOM", "conversion_factor": line.conversion_factor,
                    "stock_quantity_ordered": line.stock_quantity, "line_amount": line.line_total,
                    **progress,
                })
            return {"basis": "Persisted sales-order-line ordered, delivered, invoiced, and returned quantity snapshots.", "rows": result}

        if name == "inactive-customers":
            last = select(func.max(SalesInvoice.invoice_date)).where(SalesInvoice.tenant_id == tenant_id, SalesInvoice.customer_id == Customer.customer_id, SalesInvoice.status != "CANCELLED").scalar_subquery()
            rows = (await db.execute(select(Customer, last.label("last_sale")).where(Customer.tenant_id == tenant_id, Customer.is_active.is_(True)).order_by(last.asc().nulls_first()))).all()
            return [{"customer_id": str(c.customer_id), "customer_code": c.customer_code, "customer_name": c.customer_name, "last_invoice_date": d, "days_since_last_sale": (as_of_date - d).days if d else None} for c, d in rows]

        if name == "stock-projected-quantity":
            received_for_po_line = select(func.coalesce(func.sum(GoodsReceiptNoteItem.quantity_accepted), 0)).join(GoodsReceiptNote, GoodsReceiptNote.grn_id == GoodsReceiptNoteItem.grn_id).where(GoodsReceiptNoteItem.tenant_id == tenant_id, GoodsReceiptNote.tenant_id == tenant_id, GoodsReceiptNoteItem.po_item_id == PurchaseOrderItem.item_line_id, GoodsReceiptNote.status != "CANCELLED").correlate(PurchaseOrderItem).scalar_subquery()
            delivered_for_order_line = select(func.coalesce(func.sum(DeliveryNoteItem.quantity), 0)).join(DeliveryNote, DeliveryNote.delivery_note_id == DeliveryNoteItem.delivery_note_id).where(DeliveryNoteItem.tenant_id == tenant_id, DeliveryNote.tenant_id == tenant_id, DeliveryNoteItem.order_item_id == SalesOrderItem.order_item_id, DeliveryNote.status != "CANCELLED").correlate(SalesOrderItem).scalar_subquery()
            demand = select(func.coalesce(func.sum(func.greatest(SalesOrderItem.quantity - delivered_for_order_line, 0)), 0)).join(SalesOrder, SalesOrder.order_id == SalesOrderItem.order_id).where(SalesOrderItem.tenant_id == tenant_id, SalesOrder.tenant_id == tenant_id, SalesOrderItem.item_id == Item.item_id, SalesOrder.status.notin_(("CANCELLED", "COMPLETED"))).scalar_subquery()
            supply = select(func.coalesce(func.sum(func.greatest(PurchaseOrderItem.quantity - received_for_po_line, 0)), 0)).join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id).where(PurchaseOrderItem.tenant_id == tenant_id, PurchaseOrder.tenant_id == tenant_id, PurchaseOrderItem.item_id == Item.item_id, PurchaseOrder.status.notin_(("CANCELLED", "COMPLETED"))).scalar_subquery()
            rows = (await db.execute(select(Item, func.coalesce(func.sum(StockLevel.current_qty), 0).label("on_hand"), func.coalesce(func.sum(StockLevel.reserved_qty), 0).label("reserved"), demand.label("demand"), supply.label("supply")).outerjoin(StockLevel, (StockLevel.item_id == Item.item_id) & (StockLevel.tenant_id == tenant_id)).where(Item.tenant_id == tenant_id, Item.is_active.is_(True)).group_by(Item.item_id, demand, supply))).all()
            return [{"item_id": str(i.item_id), "item_code": i.item_code, "item_name": i.item_name, "on_hand": on_hand, "reserved": reserved, "open_sales_qty": d, "open_purchase_qty": s, "projected_qty": on_hand - reserved - d + s} for i, on_hand, reserved, d, s in rows]

        if name == "stock-ageing":
            cutoff = as_of_date + timedelta(days=1)
            consumed_by_date = select(func.coalesce(func.sum(StockLayerConsumption.quantity), 0))\
                .join(StockLedgerEntry, StockLedgerEntry.entry_id == StockLayerConsumption.outgoing_entry_id)\
                .where(
                    StockLayerConsumption.tenant_id == tenant_id,
                    StockLayerConsumption.layer_id == StockValuationLayer.layer_id,
                    StockLayerConsumption.is_reversed.is_(False),
                    StockLedgerEntry.tenant_id == tenant_id,
                    StockLedgerEntry.posting_datetime < cutoff,
                    StockLedgerEntry.is_cancelled.is_(False),
                ).correlate(StockValuationLayer).scalar_subquery()
            remaining_as_of = StockValuationLayer.received_qty - consumed_by_date
            stmt = select(
                StockValuationLayer, Item.item_code, Item.item_name, remaining_as_of.label("remaining_as_of"),
            ).join(Item, (Item.item_id == StockValuationLayer.item_id) & (Item.tenant_id == tenant_id)).where(
                StockValuationLayer.tenant_id == tenant_id,
                StockValuationLayer.is_cancelled.is_(False),
                StockValuationLayer.received_at < cutoff,
                remaining_as_of > 0,
            ).order_by(StockValuationLayer.received_at, StockValuationLayer.layer_id)
            rows = (await db.execute(stmt)).all()
            return {
                "method": "Persisted FIFO layers; remaining quantities are depleted transactionally by stock issues.",
                "rows": [{
                    "layer_id": str(layer.layer_id), "item_id": str(layer.item_id),
                    "item_code": code, "item_name": label,
                    "warehouse_id": str(layer.warehouse_id), "receipt_date": layer.received_at.date(),
                    "receipt_qty": layer.received_qty, "remaining_qty": remaining,
                    "unit_cost": layer.unit_cost, "remaining_value": remaining * layer.unit_cost,
                    "age_days": (as_of_date - layer.received_at.date()).days,
                    "source_document_type": layer.source_document_type,
                    "source_document_id": str(layer.source_document_id) if layer.source_document_id else None,
                    "estimated_cost": layer.source_document_type == "OPENING_BALANCE",
                } for layer, code, label, remaining in rows],
            }

        if name == "stock-analytics":
            stmt = select(Item.item_id, Item.item_code, Item.item_name, Item.category, func.coalesce(func.sum(StockLevel.current_qty), 0).label("quantity"), func.coalesce(func.sum(StockLevel.current_qty * StockLevel.valuation_rate), 0).label("value"), func.coalesce(func.sum(StockLevel.reserved_qty), 0).label("reserved"))\
                .outerjoin(StockLevel, (StockLevel.item_id == Item.item_id) & (StockLevel.tenant_id == tenant_id)).where(Item.tenant_id == tenant_id).group_by(Item.item_id, Item.item_code, Item.item_name, Item.category).order_by(func.sum(StockLevel.current_qty * StockLevel.valuation_rate).desc())
            return [{"item_id": str(i), "item_code": c, "item_name": n, "category": cat, "quantity": qty, "stock_value": val, "reserved": res} for i, c, n, cat, qty, val, res in (await db.execute(stmt)).all()]

        if name == "hr-analytics":
            statuses = (await db.execute(select(Employee.status, func.count()).where(Employee.tenant_id == tenant_id).group_by(Employee.status))).all()
            since = as_of_date - timedelta(days=365)
            exits = await db.scalar(select(func.count()).select_from(EmployeeSeparation).where(EmployeeSeparation.tenant_id == tenant_id, EmployeeSeparation.resignation_date >= since, EmployeeSeparation.resignation_date <= as_of_date)) or 0
            total = sum(n for _, n in statuses)
            return {"headcount": total, "by_status": {s: n for s, n in statuses}, "separations_last_12_months": exits, "attrition_rate_pct": (Decimal(exits * 100) / Decimal(total)).quantize(Decimal("0.01")) if total else Decimal("0.00")}

        if name == "leave-balance-summary":
            used = select(func.coalesce(func.sum(LeaveApplication.total_leave_days), 0)).where(LeaveApplication.tenant_id == tenant_id, LeaveApplication.employee_id == LeaveAllocation.employee_id, LeaveApplication.leave_type_id == LeaveAllocation.leave_type_id, LeaveApplication.status == "APPROVED", LeaveApplication.from_date >= LeaveAllocation.from_date, LeaveApplication.from_date <= LeaveAllocation.to_date).correlate(LeaveAllocation).scalar_subquery()
            stmt = select(Employee, LeaveType, LeaveAllocation, used.label("used")).join(LeaveAllocation, (LeaveAllocation.employee_id == Employee.employee_id) & (LeaveAllocation.tenant_id == tenant_id)).join(LeaveType, (LeaveType.leave_type_id == LeaveAllocation.leave_type_id) & (LeaveType.tenant_id == tenant_id)).where(Employee.tenant_id == tenant_id, LeaveAllocation.fiscal_year == (fiscal_year or as_of_date.year))
            return [{"employee_id": str(e.employee_id), "employee_code": e.employee_code, "employee_name": f"{e.first_name} {e.last_name}", "leave_type": lt.type_name, "allocated": Decimal(str(a.total_leaves_allocated or 0)) + Decimal(str(a.carry_forward_leaves or 0)), "used": Decimal(str(u or 0)), "balance": Decimal(str(a.total_leaves_allocated or 0)) + Decimal(str(a.carry_forward_leaves or 0)) - Decimal(str(u or 0))} for e, lt, a, u in (await db.execute(stmt)).all()]

        if name == "employee-birthdays":
            m = month or as_of_date.month
            rows = (await db.scalars(select(Employee).where(Employee.tenant_id == tenant_id, Employee.is_active.is_(True), Employee.date_of_birth.is_not(None), extract("month", Employee.date_of_birth) == m).order_by(extract("day", Employee.date_of_birth)))).all()
            return [{"employee_id": str(e.employee_id), "employee_code": e.employee_code, "employee_name": f"{e.first_name} {e.last_name}", "date_of_birth": e.date_of_birth} for e in rows]

        if name == "recruitment-funnel":
            roles = await db.scalar(select(func.count()).select_from(RecruitmentRole).where(RecruitmentRole.tenant_id == tenant_id, RecruitmentRole.status == "OPEN")) or 0
            apps = (await db.execute(select(CandidateApplication.status, func.count()).where(CandidateApplication.tenant_id == tenant_id).group_by(CandidateApplication.status))).all()
            interviews = (await db.execute(select(Interview.outcome, func.count()).where(Interview.tenant_id == tenant_id).group_by(Interview.outcome))).all()
            return {"open_roles": roles, "applications_by_status": {s: n for s, n in apps}, "interviews_by_outcome": {s or "UNSET": n for s, n in interviews}}

        if name in {"support-sla-compliance", "support-agent-performance"}:
            if name == "support-sla-compliance":
                stmt = select(Issue.priority, func.count().label("total"), func.sum(case((Issue.sla_status.in_(("WITHIN_SLA", "FULFILLED")), 1), else_=0)).label("compliant"), func.sum(case((Issue.sla_status.in_(("RESPONSE_BREACHED", "RESOLUTION_BREACHED")), 1), else_=0)).label("breached")).where(Issue.tenant_id == tenant_id, *self._period(func.date(Issue.created_at), *period)).group_by(Issue.priority)
                return [{"priority": p, "total": n, "compliant": c or 0, "breached": b or 0, "compliance_pct": (Decimal(c or 0) * 100 / Decimal(n)).quantize(Decimal("0.01")) if n else Decimal("0.00")} for p, n, c, b in (await db.execute(stmt)).all()]
            stmt = select(Issue.assigned_to_id, func.count().label("tickets"), func.sum(case((Issue.status.in_(("RESOLVED", "CLOSED")), 1), else_=0)).label("resolved"), func.sum(case((Issue.sla_status.in_(("RESPONSE_BREACHED", "RESOLUTION_BREACHED")), 1), else_=0)).label("breached"), func.avg(extract("epoch", Issue.first_responded_on - Issue.created_at) / 3600).label("avg_response_hours"), func.avg(extract("epoch", Issue.resolution_date - Issue.created_at) / 3600).label("avg_resolution_hours")).where(Issue.tenant_id == tenant_id, *self._period(func.date(Issue.created_at), *period)).group_by(Issue.assigned_to_id).order_by(func.count().desc())
            rows = (await db.execute(stmt)).all()
            return [{"agent_id": str(a) if a else None, "tickets": n, "resolved": r or 0, "sla_breaches": b or 0, "avg_response_hours": response, "avg_resolution_hours": resolution} for a, n, r, b, response, resolution in rows]

        raise ValueError(f"Unknown report: {name}")


enterprise_reports_service = EnterpriseReportsService()
