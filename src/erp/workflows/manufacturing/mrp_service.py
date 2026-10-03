"""Material Requirements Planning (MRP) and Production Planning Engine."""

from datetime import date
from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, StockLevel
from erp.db.models.manufacturing import (
    BOM,
    BOMItem,
    ProductionPlan,
    ProductionPlanItem,
    WorkOrder,
)

logger = logging.getLogger(__name__)


class MRPService:
    """Core domain logic for Production Plans, multi-level BOM explosion, and Work Order generation."""

    async def create_production_plan(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        plan_number: str,
        items: list[dict[str, Any]],
        posting_date: date | None = None,
    ) -> ProductionPlan:
        """Creates a Production Plan from sales demand or direct planning requirements."""
        if not posting_date:
            posting_date = date.today()

        plan = ProductionPlan(
            tenant_id=tenant_id,
            plan_number=plan_number.strip(),
            posting_date=posting_date,
            status="DRAFT",
            total_planned_qty=Decimal("0.0000"),
        )
        session.add(plan)
        await session.flush()

        total_qty = Decimal("0.0000")
        for it in items:
            item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty = Decimal(str(it["planned_qty"]))
            total_qty += qty

            bom_id = uuid.UUID(str(it["bom_id"])) if it.get("bom_id") else None
            if not bom_id:
                # Find default active BOM
                default_bom = (
                    await session.execute(
                        select(BOM).where(
                            BOM.tenant_id == tenant_id,
                            BOM.item_id == item_id,
                            BOM.is_default.is_(True),
                            BOM.is_active.is_(True),
                        )
                    )
                ).scalars().first()
                if default_bom:
                    bom_id = default_bom.bom_id

            so_id = uuid.UUID(str(it["sales_order_id"])) if it.get("sales_order_id") else None

            plan_item = ProductionPlanItem(
                tenant_id=tenant_id,
                plan_id=plan.plan_id,
                item_id=item_id,
                bom_id=bom_id,
                sales_order_id=so_id,
                planned_qty=qty,
                produced_qty=Decimal("0.0000"),
            )
            session.add(plan_item)

        plan.total_planned_qty = total_qty
        await session.flush()
        return await self.get_production_plan(session, tenant_id, plan.plan_id)  # type: ignore

    async def get_production_plan(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
    ) -> ProductionPlan | None:
        """Retrieves Production Plan with items."""
        stmt = (
            select(ProductionPlan)
            .options(
                selectinload(ProductionPlan.items),
            )
            .where(
                ProductionPlan.tenant_id == tenant_id,
                ProductionPlan.plan_id == plan_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_production_plans(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[ProductionPlan]:
        """Lists Production Plans."""
        stmt = (
            select(ProductionPlan)
            .options(selectinload(ProductionPlan.items))
            .where(ProductionPlan.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(ProductionPlan.status == status.upper())
        stmt = stmt.order_by(ProductionPlan.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def explode_material_requirements(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Recursively explodes BOMs for all items in plan to compute gross requirements and stock shortages."""
        plan = await self.get_production_plan(session, tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Production Plan '{plan_id}' not found.")

        # Dictionary mapping component_item_id -> Decimal gross required
        gross_requirements: dict[uuid.UUID, Decimal] = {}

        async def _explode_bom(bom_id: uuid.UUID, multiplier_qty: Decimal):
            bom_stmt = (
                select(BOM)
                .options(selectinload(BOM.items))
                .where(BOM.tenant_id == tenant_id, BOM.bom_id == bom_id)
            )
            bom = (await session.execute(bom_stmt)).scalar_one_or_none()
            if not bom or not bom.items:
                return

            bom_base = bom.quantity if bom.quantity > Decimal("0.0000") else Decimal("1.0000")
            ratio = multiplier_qty / bom_base

            for c in bom.items:
                comp_req = c.quantity * ratio
                if c.scrap_percentage > Decimal("0.0000"):
                    comp_req = comp_req * (Decimal("1.0") + (c.scrap_percentage / Decimal("100.0")))

                gross_requirements[c.item_id] = gross_requirements.get(c.item_id, Decimal("0.0000")) + comp_req

                # Check if this component has its own sub-assembly BOM to recurse
                sub_bom_id = c.bom_sub_assembly_id
                if not sub_bom_id:
                    sub_bom = (
                        await session.execute(
                            select(BOM).where(
                                BOM.tenant_id == tenant_id,
                                BOM.item_id == c.item_id,
                                BOM.is_default.is_(True),
                                BOM.bom_id != bom_id,
                            )
                        )
                    ).scalars().first()
                    if sub_bom:
                        sub_bom_id = sub_bom.bom_id

                if sub_bom_id:
                    await _explode_bom(sub_bom_id, comp_req)

        items_without_bom = []
        for p_item in plan.items:
            b_id = p_item.bom_id
            if not b_id:
                # Attempt to find default BOM
                d_bom = (
                    await session.execute(
                        select(BOM).where(
                            BOM.tenant_id == tenant_id,
                            BOM.item_id == p_item.item_id,
                            BOM.is_default.is_(True),
                        )
                    )
                ).scalars().first()
                if d_bom:
                    b_id = d_bom.bom_id
                else:
                    item_obj = (
                        await session.execute(
                            select(Item).where(Item.tenant_id == tenant_id, Item.item_id == p_item.item_id)
                        )
                    ).scalar_one_or_none()
                    items_without_bom.append({
                        "item_id": str(p_item.item_id),
                        "item_name": item_obj.item_name if item_obj else "Unknown Item",
                        "item_code": item_obj.item_code if item_obj else "N/A",
                    })

            if b_id:
                await _explode_bom(b_id, p_item.planned_qty)

        # Retrieve stock levels and item metadata
        exploded_items = []
        for c_item_id, gross_qty in gross_requirements.items():
            item = (
                await session.execute(
                    select(Item).where(Item.tenant_id == tenant_id, Item.item_id == c_item_id)
                )
            ).scalar_one_or_none()

            # Sum stock levels across warehouses
            stock_stmt = select(
                func.coalesce(func.sum(StockLevel.current_qty), Decimal("0.0000")),
                func.coalesce(func.sum(StockLevel.reserved_qty), Decimal("0.0000")),
                func.coalesce(func.sum(StockLevel.available_qty), Decimal("0.0000")),
            ).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == c_item_id,
            )
            stock_row = (await session.execute(stock_stmt)).one()
            curr_qty = stock_row[0]
            res_qty = stock_row[1]
            avail_qty = stock_row[2]

            shortage = max(Decimal("0.0000"), gross_qty - avail_qty)

            exploded_items.append({
                "item_id": str(c_item_id),
                "item_code": item.item_code if item else "N/A",
                "item_name": item.item_name if item else "Unknown Component",
                "uom": item.stock_uom if item else "Nos",
                "gross_required_qty": float(gross_qty),
                "current_stock_qty": float(curr_qty),
                "reserved_qty": float(res_qty),
                "available_stock_qty": float(avail_qty),
                "shortage_qty": float(shortage),
            })

        return {
            "plan_id": str(plan.plan_id),
            "plan_number": plan.plan_number,
            "total_planned_qty": float(plan.total_planned_qty),
            "exploded_requirements": exploded_items,
            "items_without_bom": items_without_bom,
        }

    async def generate_work_orders_from_plan(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
    ) -> list[WorkOrder]:
        """Automatically provisions Work Orders for all line items in the production plan."""
        from erp.workflows.manufacturing.work_order_service import work_order_service

        plan = await self.get_production_plan(session, tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Production Plan '{plan_id}' not found.")

        created_orders = []
        for idx, p_item in enumerate(plan.items, start=1):
            wo_number = f"WO-{plan.plan_number}-{idx:02d}"

            # Check if WO already created for this plan item
            existing = (
                await session.execute(
                    select(WorkOrder).where(
                        WorkOrder.tenant_id == tenant_id,
                        WorkOrder.production_plan_id == plan.plan_id,
                        WorkOrder.item_id == p_item.item_id,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                created_orders.append(existing)
                continue

            wo = await work_order_service.create_work_order(
                session=session,
                tenant_id=tenant_id,
                work_order_number=wo_number,
                item_id=p_item.item_id,
                planned_quantity=p_item.planned_qty,
                bom_id=p_item.bom_id,
                production_plan_id=plan.plan_id,
            )
            created_orders.append(wo)

        plan.status = "IN_PROCESS"
        await session.flush()
        return created_orders


mrp_service = MRPService()
