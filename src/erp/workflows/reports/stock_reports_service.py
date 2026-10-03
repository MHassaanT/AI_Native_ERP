"""Enterprise Stock, Inventory, and Production Analytics Reports Engine."""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.manufacturing import WorkOrder, Workstation
from erp.db.models.purchasing import PurchaseOrderItem, GoodsReceiptNoteItem
from erp.db.models.sales import SalesOrderItem

logger = logging.getLogger(__name__)


class StockReportsService:
    """Core inventory analytics engine for Stock Balance, Stock Ledger, Sales/Purchase Registers, and MES Analytics."""

    async def get_stock_balance(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Stock Balance Report: Item, Warehouse, Current Qty, Valuation Rate, Total Stock Value.
        """
        stmt = (
            select(StockLevel, Item, Warehouse)
            .join(Item, StockLevel.item_id == Item.item_id)
            .join(Warehouse, StockLevel.warehouse_id == Warehouse.warehouse_id)
            .where(StockLevel.tenant_id == tenant_id)
        )
        if warehouse_id:
            stmt = stmt.where(StockLevel.warehouse_id == warehouse_id)
        if item_id:
            stmt = stmt.where(StockLevel.item_id == item_id)

        rows = (await session.execute(stmt)).all()

        items_data: List[Dict[str, Any]] = []
        total_quantity = Decimal("0.0000")
        total_valuation_value = Decimal("0.0000")

        for level, item, wh in rows:
            val_value = (level.current_qty * level.valuation_rate).quantize(Decimal("0.0001"))
            total_quantity += level.current_qty
            total_valuation_value += val_value

            items_data.append({
                "item_id": str(item.item_id),
                "item_code": item.item_code,
                "item_name": item.item_name,
                "warehouse_id": str(wh.warehouse_id),
                "warehouse_name": wh.warehouse_name,
                "current_qty": level.current_qty,
                "reserved_qty": level.reserved_qty,
                "available_qty": level.available_qty,
                "valuation_rate": level.valuation_rate,
                "stock_value": val_value,
            })

        return {
            "total_items": len(items_data),
            "total_quantity": total_quantity,
            "total_valuation_value": total_valuation_value,
            "rows": items_data,
        }

    async def get_stock_ledger(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: Optional[uuid.UUID] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Stock Ledger: Chronological audit trail of inventory movements.
        """
        stmt = (
            select(StockLedgerEntry, Item, Warehouse)
            .join(Item, StockLedgerEntry.item_id == Item.item_id)
            .join(Warehouse, StockLedgerEntry.warehouse_id == Warehouse.warehouse_id)
            .where(StockLedgerEntry.tenant_id == tenant_id)
        )
        if item_id:
            stmt = stmt.where(StockLedgerEntry.item_id == item_id)
        if warehouse_id:
            stmt = stmt.where(StockLedgerEntry.warehouse_id == warehouse_id)
        if from_date:
            stmt = stmt.where(func.date(StockLedgerEntry.posting_datetime) >= from_date)
        if to_date:
            stmt = stmt.where(func.date(StockLedgerEntry.posting_datetime) <= to_date)

        stmt = stmt.order_by(StockLedgerEntry.posting_datetime.desc()).limit(limit)
        results = (await session.execute(stmt)).all()

        ledger_rows: List[Dict[str, Any]] = []
        for entry, item, wh in results:
            ledger_rows.append({
                "entry_id": str(entry.entry_id),
                "posting_datetime": entry.posting_datetime.isoformat(),
                "item_code": item.item_code,
                "item_name": item.item_name,
                "warehouse_name": wh.warehouse_name,
                "actual_qty": entry.actual_qty,
                "qty_after_transaction": entry.qty_after_transaction,
                "incoming_rate": entry.incoming_rate,
                "outgoing_rate": entry.outgoing_rate,
                "valuation_rate": entry.valuation_rate,
                "source_document_type": entry.source_document_type,
                "source_document_id": str(entry.source_document_id),
            })

        return {
            "count": len(ledger_rows),
            "rows": ledger_rows,
        }

    async def get_item_wise_sales_register(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Item-wise Sales Register aggregating sales volume, revenue, and average unit price per item.
        """
        stmt = (
            select(
                Item.item_id,
                Item.item_code,
                Item.item_name,
                func.coalesce(func.sum(SalesOrderItem.quantity), Decimal("0.0000")).label("total_qty"),
                func.coalesce(func.sum(SalesOrderItem.line_total), Decimal("0.0000")).label("total_revenue"),
            )
            .join(Item, SalesOrderItem.item_id == Item.item_id)
            .where(SalesOrderItem.tenant_id == tenant_id)
            .group_by(Item.item_id, Item.item_code, Item.item_name)
        )
        res = (await session.execute(stmt)).all()

        rows = []
        total_sales_volume = Decimal("0.0000")
        total_sales_revenue = Decimal("0.0000")

        for row in res:
            total_sales_volume += row.total_qty
            total_sales_revenue += row.total_revenue
            avg_rate = (row.total_revenue / row.total_qty) if row.total_qty > 0 else Decimal("0.0000")
            rows.append({
                "item_id": str(row.item_id),
                "item_code": row.item_code,
                "item_name": row.item_name,
                "total_quantity": row.total_qty,
                "total_revenue": row.total_revenue,
                "average_price": avg_rate.quantize(Decimal("0.0001")),
            })

        return {
            "total_items": len(rows),
            "total_volume": total_sales_volume,
            "total_revenue": total_sales_revenue,
            "rows": rows,
        }

    async def get_item_wise_purchase_register(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Item-wise Purchase Register aggregating procurement volume, cost, and average purchase price per item.
        """
        stmt = (
            select(
                Item.item_id,
                Item.item_code,
                Item.item_name,
                func.coalesce(func.sum(PurchaseOrderItem.quantity), Decimal("0.0000")).label("total_qty"),
                func.coalesce(func.sum(PurchaseOrderItem.line_total), Decimal("0.0000")).label("total_cost"),
            )
            .join(Item, PurchaseOrderItem.item_id == Item.item_id)
            .where(PurchaseOrderItem.tenant_id == tenant_id)
            .group_by(Item.item_id, Item.item_code, Item.item_name)
        )
        res = (await session.execute(stmt)).all()

        rows = []
        total_purch_volume = Decimal("0.0000")
        total_purch_cost = Decimal("0.0000")

        for row in res:
            total_purch_volume += row.total_qty
            total_purch_cost += row.total_cost
            avg_rate = (row.total_cost / row.total_qty) if row.total_qty > 0 else Decimal("0.0000")
            rows.append({
                "item_id": str(row.item_id),
                "item_code": row.item_code,
                "item_name": row.item_name,
                "total_quantity": row.total_qty,
                "total_cost": row.total_cost,
                "average_price": avg_rate.quantize(Decimal("0.0001")),
            })

        return {
            "total_items": len(rows),
            "total_volume": total_purch_volume,
            "total_cost": total_purch_cost,
            "rows": rows,
        }

    async def get_production_analytics(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        MES & Production Analytics: Work order completion %, scrap rate, workstation utilization.
        """
        wo_stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
        work_orders = (await session.execute(wo_stmt)).scalars().all()

        total_wo = len(work_orders)
        completed_wo = sum(1 for wo in work_orders if wo.status == "COMPLETED")
        in_progress_wo = sum(1 for wo in work_orders if wo.status in ("IN_PROGRESS", "RELEASED"))
        planned_qty = sum((wo.qty_planned for wo in work_orders), Decimal("0.0000"))
        produced_qty = sum((wo.qty_produced for wo in work_orders), Decimal("0.0000"))

        completion_rate = ((completed_wo / total_wo) * 100) if total_wo > 0 else 0.0
        yield_rate = (float(produced_qty / planned_qty) * 100.0) if planned_qty > 0 else 100.0

        # Workstations
        ws_stmt = select(Workstation).where(Workstation.tenant_id == tenant_id)
        workstations = (await session.execute(ws_stmt)).scalars().all()

        ws_data = [
            {
                "workstation_id": str(ws.workstation_id),
                "workstation_name": ws.name,
                "status": ws.status,
                "hour_rate": ws.hour_rate,
            }
            for ws in workstations
        ]

        return {
            "total_work_orders": total_wo,
            "completed_work_orders": completed_wo,
            "in_progress_work_orders": in_progress_wo,
            "completion_rate_pct": round(completion_rate, 2),
            "total_planned_qty": planned_qty,
            "total_produced_qty": produced_qty,
            "yield_rate_pct": round(yield_rate, 2),
            "scrap_rate_pct": round(max(100.0 - yield_rate, 0.0), 2),
            "workstations": ws_data,
        }


stock_reports_service = StockReportsService()
