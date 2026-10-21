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

from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel
from erp.db.models.purchasing import (
    GoodsReceiptNote, GoodsReceiptNoteItem, MaterialRequest, MaterialRequestItem,
    PurchaseOrder, PurchaseOrderItem, Supplier, SupplierInvoice, SupplierInvoiceItem,
)
from erp.db.models.sales import (
    Customer, DeliveryNote, DeliveryNoteItem, SalesInvoice, SalesInvoiceItem,
    SalesOrder, SalesOrderItem, SalesQuotation,
)
from erp.db.models.phase_b import SalesPartner, SalesTeam
from erp.db.models.support import Issue
from erp.db.models.hr import (
    Employee, EmployeeSeparation, LeaveAllocation, LeaveApplication, LeaveType,
)
from erp.db.models.recruitment import RecruitmentRole, CandidateApplication
from erp.db.models.hr_deep import Interview


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

    async def run(self, name: str, db: AsyncSession, tenant_id: uuid.UUID,
                  from_date: date | None = None, to_date: date | None = None,
                  as_of_date: date | None = None, month: int | None = None,
                  fiscal_year: int | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        as_of_date = as_of_date or to_date or date.today()
        period = (from_date, to_date)

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
            # F8 is represented as supplier/item sourced-sales context because the
            # current Customer/Item model does not persist supplier attribution on sales.
            return {"attribution_note": "Sales are not linked to suppliers in the current schema; rows show supplier-sourced purchase activity by item, not supplier-attributed revenue.",
                    "rows": [{"period": r.period.date().isoformat(), "supplier_id": str(r.supplier_id), "supplier_name": r.supplier_name, "item_id": str(r.item_id), "item_code": r.item_code, "item_name": r.item_name, "quantity": r.quantity, "purchase_amount": r.amount} for r in rows]}

        if name == "purchase-order-analytics":
            overdue_cutoff = as_of_date - timedelta(days=30)
            stmt = select(PurchaseOrder.po_id, PurchaseOrder.po_number, Supplier.supplier_name, PurchaseOrder.order_date, PurchaseOrder.status, PurchaseOrder.total_amount, (PurchaseOrder.order_date < overdue_cutoff).label("overdue"))\
                .join(Supplier, Supplier.supplier_id == PurchaseOrder.supplier_id).where(PurchaseOrder.tenant_id == tenant_id, Supplier.tenant_id == tenant_id, *self._period(PurchaseOrder.order_date, *period)).order_by(PurchaseOrder.order_date)
            return [{"po_id": str(r.po_id), "po_number": r.po_number, "supplier": r.supplier_name, "order_date": r.order_date, "status": r.status, "total_amount": r.total_amount, "overdue_after_days": 30, "overdue": bool(r.overdue and r.status not in ("COMPLETED", "CANCELLED"))} for r in (await db.execute(stmt)).all()]

        if name == "procurement-tracker":
            stmt = select(MaterialRequest.mr_id, MaterialRequest.mr_number, MaterialRequest.schedule_date, MaterialRequest.status, Item.item_code, Item.item_name, MaterialRequestItem.quantity, MaterialRequestItem.ordered_qty, PurchaseOrder.po_number, GoodsReceiptNote.grn_number, func.coalesce(func.sum(GoodsReceiptNoteItem.quantity_accepted), 0).label("received"))\
                .join(MaterialRequestItem, MaterialRequestItem.mr_id == MaterialRequest.mr_id).join(Item, Item.item_id == MaterialRequestItem.item_id)\
                .outerjoin(PurchaseOrderItem, (PurchaseOrderItem.item_id == Item.item_id) & (PurchaseOrderItem.tenant_id == tenant_id)).outerjoin(PurchaseOrder, (PurchaseOrder.po_id == PurchaseOrderItem.po_id) & (PurchaseOrder.tenant_id == tenant_id) & (PurchaseOrder.order_date >= MaterialRequest.schedule_date))\
                .outerjoin(GoodsReceiptNote, (GoodsReceiptNote.po_id == PurchaseOrder.po_id) & (GoodsReceiptNote.tenant_id == tenant_id) & (GoodsReceiptNote.receipt_date >= PurchaseOrder.order_date)).outerjoin(GoodsReceiptNoteItem, (GoodsReceiptNoteItem.grn_id == GoodsReceiptNote.grn_id) & (GoodsReceiptNoteItem.item_id == Item.item_id) & (GoodsReceiptNoteItem.tenant_id == tenant_id))\
                .where(MaterialRequest.tenant_id == tenant_id, MaterialRequestItem.tenant_id == tenant_id, Item.tenant_id == tenant_id, *self._period(MaterialRequest.schedule_date, *period))\
                .group_by(MaterialRequest.mr_id, MaterialRequest.mr_number, MaterialRequest.schedule_date, MaterialRequest.status, Item.item_code, Item.item_name, MaterialRequestItem.quantity, MaterialRequestItem.ordered_qty, PurchaseOrder.po_number, GoodsReceiptNote.grn_number).order_by(MaterialRequest.schedule_date)
            return [{"mr_id": str(r.mr_id), "mr_number": r.mr_number, "schedule_date": r.schedule_date, "status": r.status, "item_code": r.item_code, "item_name": r.item_name, "requested_qty": r.quantity, "ordered_qty": r.ordered_qty, "po_number": r.po_number, "grn_number": r.grn_number, "accepted_qty": r.received} for r in (await db.execute(stmt)).all()]

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
            ordered = select(func.coalesce(func.sum(SalesOrderItem.quantity), 0)).where(SalesOrderItem.tenant_id == tenant_id, SalesOrderItem.order_id == SalesOrder.order_id).scalar_subquery()
            shipped = select(func.coalesce(func.sum(DeliveryNoteItem.quantity), 0)).join(DeliveryNote, DeliveryNote.delivery_note_id == DeliveryNoteItem.delivery_note_id).where(DeliveryNote.tenant_id == tenant_id, DeliveryNoteItem.tenant_id == tenant_id, DeliveryNote.order_id == SalesOrder.order_id, DeliveryNote.status != "CANCELLED").scalar_subquery()
            billed = select(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).where(SalesInvoice.tenant_id == tenant_id, SalesInvoice.order_id == SalesOrder.order_id, SalesInvoice.status != "CANCELLED").scalar_subquery()
            rows = (await db.execute(select(SalesOrder, Customer.customer_name, ordered.label("ordered_qty"), shipped.label("shipped_qty"), billed.label("billed_amount")).join(Customer, Customer.customer_id == SalesOrder.customer_id).where(SalesOrder.tenant_id == tenant_id, Customer.tenant_id == tenant_id, *self._period(SalesOrder.order_date, *period)))).all()
            return [{"order_id": str(o.order_id), "order_number": o.order_number, "customer": c, "status": o.status, "delivery_date": o.delivery_date, "total_amount": o.total_amount, "ordered_qty": oq, "shipped_qty": sq, "pending_delivery_qty": max(Decimal("0"), oq - sq), "billed_amount": ba, "pending_billing_amount": max(Decimal("0"), o.total_amount - ba)} for o, c, oq, sq, ba in rows]

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
            # FIFO approximation from positive receipts that remain represented by
            # current levels; exact layer depletion is unavailable in this schema.
            current_stock = select(StockLevel.item_id.label("item_id"), func.sum(StockLevel.current_qty).label("current_qty")).where(StockLevel.tenant_id == tenant_id, StockLevel.is_quarantined.is_(False)).group_by(StockLevel.item_id).subquery()
            stmt = select(Item.item_id, Item.item_code, Item.item_name, StockLedgerEntry.posting_datetime, StockLedgerEntry.actual_qty, StockLedgerEntry.incoming_rate, current_stock.c.current_qty).join(current_stock, current_stock.c.item_id == Item.item_id).join(StockLedgerEntry, (StockLedgerEntry.item_id == Item.item_id) & (StockLedgerEntry.tenant_id == tenant_id)).where(Item.tenant_id == tenant_id, StockLedgerEntry.actual_qty > 0, StockLedgerEntry.is_cancelled.is_(False), current_stock.c.current_qty > 0).order_by(StockLedgerEntry.posting_datetime)
            rows = (await db.execute(stmt)).all()
            return {"method": "FIFO receipt chronology; remaining layer quantities are estimated because receipt-to-consumption layer balances are not persisted", "rows": [{"item_id": str(i), "item_code": code, "item_name": label, "receipt_date": dt.date(), "receipt_qty": qty, "incoming_rate": rate, "current_qty": current, "age_days": (as_of_date - dt.date()).days} for i, code, label, dt, qty, rate, current in rows]}

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
