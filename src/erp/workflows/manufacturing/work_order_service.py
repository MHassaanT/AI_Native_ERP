"""Work Order Service: Staging materials to WIP, manufacturing completion, and GL valuation posting."""

from datetime import UTC, date, datetime
from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.manufacturing import BOM, JobCard, WorkOrder
from erp.workflows.manufacturing.bom_service import bom_service
from erp.workflows.manufacturing.job_card_service import job_card_service
from erp.workflows.stock.stock_entry_service import StockEntryService

logger = logging.getLogger(__name__)


class WorkOrderService:
    """Core domain logic for Work Orders, Material Staging (Stores -> WIP), and Backflush Manufacture."""

    def __init__(self):
        self.stock_entry_service = StockEntryService()

    async def _resolve_warehouses(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        source_wh_id: uuid.UUID | None,
        wip_wh_id: uuid.UUID | None,
        fg_wh_id: uuid.UUID | None,
        scrap_wh_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID | None]:
        """Auto-resolves default factory warehouses if not specified."""
        all_whs = (
            await session.execute(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.is_active.is_(True),
                )
            )
        ).scalars().all()

        if not all_whs:
            # Fallback: create default warehouses for tenant
            wh_stores = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-STORES",
                warehouse_name="Stores - Raw Materials",
                is_active=True,
            )
            wh_wip = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-WIP",
                warehouse_name="Shop Floor - Work In Progress",
                is_active=True,
            )
            wh_fg = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-FG",
                warehouse_name="Finished Goods Warehouse",
                is_active=True,
            )
            wh_scrap = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-SCRAP",
                warehouse_name="Scrap & Quarantine",
                is_quarantine=True,
                is_active=True,
            )
            session.add_all([wh_stores, wh_wip, wh_fg, wh_scrap])
            await session.flush()
            all_whs = [wh_stores, wh_wip, wh_fg, wh_scrap]

        resolved_source = source_wh_id
        resolved_wip = wip_wh_id
        resolved_fg = fg_wh_id
        resolved_scrap = scrap_wh_id

        # Search matching by code/name heuristics
        for wh in all_whs:
            code = (wh.warehouse_code or "").upper()
            name = (wh.warehouse_name or "").upper()
            if not resolved_source and any(k in code or k in name for k in ("STORE", "RAW", "INCOMING", "MAIN")):
                resolved_source = wh.warehouse_id
            if not resolved_wip and any(k in code or k in name for k in ("WIP", "PROGRESS", "FLOOR", "PRODUCTION")):
                resolved_wip = wh.warehouse_id
            if not resolved_fg and any(k in code or k in name for k in ("FG", "FINISHED", "OUTPUT", "GOODS")):
                resolved_fg = wh.warehouse_id
            if not resolved_scrap and any(k in code or k in name for k in ("SCRAP", "WASTE", "DEFECT")):
                resolved_scrap = wh.warehouse_id

        # Fallbacks to ensure non-null
        fallback_id = all_whs[0].warehouse_id
        resolved_source = resolved_source or fallback_id
        resolved_wip = resolved_wip or fallback_id
        resolved_fg = resolved_fg or fallback_id

        return resolved_source, resolved_wip, resolved_fg, resolved_scrap

    async def create_work_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order_number: str,
        item_id: uuid.UUID,
        planned_quantity: Decimal,
        bom_id: uuid.UUID | None = None,
        workstation_id: uuid.UUID | None = None,
        source_warehouse_id: uuid.UUID | None = None,
        wip_warehouse_id: uuid.UUID | None = None,
        fg_warehouse_id: uuid.UUID | None = None,
        scrap_warehouse_id: uuid.UUID | None = None,
        production_plan_id: uuid.UUID | None = None,
    ) -> WorkOrder:
        """Provisions a Work Order, sets up staging routes, and generates Job Cards."""
        # Find BOM
        bom = None
        if bom_id:
            bom = await bom_service.get_bom(session, tenant_id, bom_id)
        if not bom:
            bom = (
                await session.execute(
                    select(BOM)
                    .options(
                        selectinload(BOM.items),
                        selectinload(BOM.operations),
                    )
                    .where(
                        BOM.tenant_id == tenant_id,
                        BOM.item_id == item_id,
                        BOM.is_default.is_(True),
                        BOM.is_active.is_(True),
                    )
                )
            ).scalars().first()

        s_wh, wip_wh, fg_wh, sc_wh = await self._resolve_warehouses(
            session, tenant_id, source_warehouse_id, wip_warehouse_id, fg_warehouse_id, scrap_warehouse_id
        )

        wo = WorkOrder(
            tenant_id=tenant_id,
            work_order_number=work_order_number.strip(),
            production_plan_id=production_plan_id,
            item_id=item_id,
            bom_id=bom.bom_id if bom else bom_id,
            workstation_id=workstation_id,
            source_warehouse_id=s_wh,
            wip_warehouse_id=wip_wh,
            fg_warehouse_id=fg_wh,
            scrap_warehouse_id=sc_wh,
            planned_quantity=planned_quantity,
            produced_quantity=Decimal("0.0000"),
            material_transferred_for_mfg=False,
            status="SCHEDULED",
        )
        session.add(wo)
        await session.flush()

        # Automatically generate Job Cards for BOM operations
        if bom and bom.operations:
            await job_card_service.generate_job_cards_for_work_order(
                session=session,
                tenant_id=tenant_id,
                work_order=wo,
                bom=bom,
            )

        await session.flush()
        return await self.get_work_order(session, tenant_id, wo.work_order_id)  # type: ignore

    async def stage_materials_to_wip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Creates and posts MATERIAL_TRANSFER Stock Entry (Stores -> WIP)."""
        wo = await self.get_work_order(session, tenant_id, work_order_id)
        if not wo:
            raise ValueError(f"Work Order '{work_order_id}' not found.")

        if wo.status in ("COMPLETED", "CANCELLED"):
            raise ValueError(f"Cannot stage materials for Work Order in '{wo.status}' status.")

        bom = None
        if wo.bom_id:
            bom = await bom_service.get_bom(session, tenant_id, wo.bom_id)
        if not bom or not bom.items:
            raise ValueError("No Bill of Materials or components associated with this Work Order.")

        bom_base = bom.quantity if bom.quantity > Decimal("0.0000") else Decimal("1.0000")
        ratio = wo.planned_quantity / bom_base

        staging_items = []
        for c in bom.items:
            req_qty = c.quantity * ratio
            if c.scrap_percentage > Decimal("0.0000"):
                req_qty = req_qty * (Decimal("1.0") + (c.scrap_percentage / Decimal("100.0")))

            staging_items.append({
                "item_id": str(c.item_id),
                "s_warehouse_id": str(wo.source_warehouse_id),
                "t_warehouse_id": str(wo.wip_warehouse_id),
                "qty": str(req_qty),
                "basic_rate": str(c.rate),
            })

        entry_number = f"ST-MAT-TRANSFER-{wo.work_order_number}"
        entry = await self.stock_entry_service.create_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_number=entry_number,
            stock_entry_type="MATERIAL_TRANSFER",
            purpose=f"Material Staging to WIP for {wo.work_order_number}",
            from_warehouse_id=wo.source_warehouse_id,
            to_warehouse_id=wo.wip_warehouse_id,
            items=staging_items,
        )

        submitted_entry = await self.stock_entry_service.submit_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_id=entry.entry_id,
        )

        wo.material_transferred_for_mfg = True
        wo.status = "IN_PROCESS"
        if not wo.actual_start_time:
            wo.actual_start_time = datetime.now(UTC)

        await session.flush()
        return {
            "work_order_id": str(wo.work_order_id),
            "work_order_number": wo.work_order_number,
            "status": wo.status,
            "material_transferred_for_mfg": wo.material_transferred_for_mfg,
            "stock_entry_number": submitted_entry.entry_number,
            "items_staged_count": len(staging_items),
        }

    async def complete_manufacture(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order_id: uuid.UUID,
        produced_quantity: Decimal | None = None,
        scrap_quantity: Decimal | None = None,
    ) -> dict[str, Any]:
        """Backflushes materials from WIP, receives finished goods into FG, and posts balanced GL entries."""
        wo = await self.get_work_order(session, tenant_id, work_order_id)
        if not wo:
            raise ValueError(f"Work Order '{work_order_id}' not found.")

        if wo.status == "COMPLETED":
            raise ValueError(f"Work Order '{wo.work_order_number}' is already COMPLETED.")

        prod_qty = produced_quantity or (wo.planned_quantity - wo.produced_quantity)
        if prod_qty <= Decimal("0.0000"):
            prod_qty = wo.planned_quantity

        bom = None
        if wo.bom_id:
            bom = await bom_service.get_bom(session, tenant_id, wo.bom_id)

        bom_base = bom.quantity if (bom and bom.quantity > Decimal("0.0000")) else Decimal("1.0000")
        ratio = prod_qty / bom_base

        mfg_items = []
        total_valuation = Decimal("0.0000")

        # 1. Component consumption lines (from WIP warehouse)
        if bom and bom.items:
            for c in bom.items:
                c_qty = c.quantity * ratio
                if c.scrap_percentage > Decimal("0.0000"):
                    c_qty = c_qty * (Decimal("1.0") + (c.scrap_percentage / Decimal("100.0")))
                line_val = c_qty * c.rate
                total_valuation += line_val

                mfg_items.append({
                    "item_id": str(c.item_id),
                    "s_warehouse_id": str(wo.wip_warehouse_id),
                    "t_warehouse_id": None,
                    "qty": str(c_qty),
                    "basic_rate": str(c.rate),
                })

        # Operating cost valuation
        unit_fg_rate = Decimal("25.0000")
        if bom and bom.total_cost > Decimal("0.0000"):
            unit_fg_rate = bom.total_cost / bom_base
            total_valuation = prod_qty * unit_fg_rate
        elif total_valuation > Decimal("0.0000"):
            unit_fg_rate = total_valuation / prod_qty
        else:
            total_valuation = prod_qty * unit_fg_rate

        # 2. Finished good line (into FG warehouse)
        mfg_items.append({
            "item_id": str(wo.item_id),
            "s_warehouse_id": None,
            "t_warehouse_id": str(wo.fg_warehouse_id),
            "qty": str(prod_qty),
            "basic_rate": str(unit_fg_rate),
        })

        # 3. Scrap byproduct lines
        if bom and bom.scrap_items and wo.scrap_warehouse_id:
            for sc in bom.scrap_items:
                sc_qty = sc.stock_qty * ratio
                mfg_items.append({
                    "item_id": str(sc.item_id),
                    "s_warehouse_id": None,
                    "t_warehouse_id": str(wo.scrap_warehouse_id),
                    "qty": str(sc_qty),
                    "basic_rate": str(sc.rate),
                })

        # Create and submit MANUFACTURE Stock Entry
        entry_number = f"ST-MANUFACTURE-{wo.work_order_number}"
        entry = await self.stock_entry_service.create_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_number=entry_number,
            stock_entry_type="MANUFACTURE",
            purpose=f"Finished product backflush for {wo.work_order_number}",
            from_warehouse_id=wo.wip_warehouse_id,
            to_warehouse_id=wo.fg_warehouse_id,
            items=mfg_items,
        )

        submitted_entry = await self.stock_entry_service.submit_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_id=entry.entry_id,
        )

        # Post balanced General Ledger entries: Dr Finished Goods / Cr WIP Inventory
        today_date = date.today()
        tx_id = uuid.uuid4()
        gl_dr = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=tx_id,
            posting_date=today_date,
            fiscal_year=today_date.year,
            fiscal_period=today_date.month,
            account_code="1350-FINISHED-GOODS",
            cost_center="MFG-PLANT-01",
            debit_amount=total_valuation,
            credit_amount=Decimal("0.0000"),
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="WORK_ORDER_COMPLETION",
            source_document_id=wo.work_order_id,
        )
        gl_cr = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=tx_id,
            posting_date=today_date,
            fiscal_year=today_date.year,
            fiscal_period=today_date.month,
            account_code="1400-WIP-INVENTORY",
            cost_center="MFG-PLANT-01",
            debit_amount=Decimal("0.0000"),
            credit_amount=total_valuation,
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="WORK_ORDER_COMPLETION",
            source_document_id=wo.work_order_id,
        )
        session.add_all([gl_dr, gl_cr])

        now_utc = datetime.now(UTC)
        wo.produced_quantity += prod_qty
        wo.status = "COMPLETED"
        wo.actual_end_time = now_utc
        if wo.actual_start_time:
            wo.lead_time_mins = Decimal(str(max(0.0, (wo.actual_end_time - wo.actual_start_time).total_seconds() / 60.0)))

        # Also complete linked job cards
        for jc in wo.job_cards:
            if jc.status != "COMPLETED":
                jc.status = "COMPLETED"
                jc.total_completed_qty = jc.for_quantity
                if jc.workstation_id and jc.workstation and jc.workstation.status == "IN_USE":
                    jc.workstation.status = "OPERATIONAL"

        await session.flush()
        return {
            "work_order_id": str(wo.work_order_id),
            "work_order_number": wo.work_order_number,
            "status": wo.status,
            "produced_quantity": float(wo.produced_quantity),
            "lead_time_mins": float(wo.lead_time_mins),
            "valuation_transferred": float(total_valuation),
            "stock_entry_number": submitted_entry.entry_number,
        }

    async def get_work_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        work_order_id: uuid.UUID,
    ) -> WorkOrder | None:
        """Retrieves Work Order with all travelers, operations, and logs."""
        stmt = (
            select(WorkOrder)
            .options(
                selectinload(WorkOrder.job_cards).selectinload(JobCard.operation),
                selectinload(WorkOrder.job_cards).selectinload(JobCard.workstation),
                selectinload(WorkOrder.job_cards).selectinload(JobCard.time_logs),
            )
            .where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.work_order_id == work_order_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_work_orders(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
        production_plan_id: uuid.UUID | None = None,
    ) -> list[WorkOrder]:
        """Lists Work Orders."""
        stmt = (
            select(WorkOrder)
            .options(
                selectinload(WorkOrder.job_cards).selectinload(JobCard.operation),
                selectinload(WorkOrder.job_cards).selectinload(JobCard.workstation),
            )
            .where(WorkOrder.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(WorkOrder.status == status.upper())
        if production_plan_id:
            stmt = stmt.where(WorkOrder.production_plan_id == production_plan_id)
        stmt = stmt.order_by(WorkOrder.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


work_order_service = WorkOrderService()
