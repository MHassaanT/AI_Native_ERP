"""Material Request (Requisition) and Automated Replenishment Service."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.purchasing import (
    MaterialRequest,
    MaterialRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
)


class RequisitionService:
    """Core domain logic for Material Requests and replenishment."""

    async def create_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_number: str,
        material_request_type: str = "PURCHASE",
        schedule_date: date | None = None,
        notes: str | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> MaterialRequest:
        """Creates a new Material Request (Requisition)."""
        if not schedule_date:
            schedule_date = date.today() + timedelta(days=7)

        req = MaterialRequest(
            tenant_id=tenant_id,
            mr_number=mr_number,
            material_request_type=material_request_type.upper(),
            schedule_date=schedule_date,
            status="DRAFT",
            notes=notes,
        )
        session.add(req)
        await session.flush()

        if items:
            for it in items:
                req_item = MaterialRequestItem(
                    tenant_id=tenant_id,
                    mr_id=req.mr_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    quantity=Decimal(str(it["quantity"])),
                    ordered_qty=Decimal("0.0000"),
                    target_warehouse_id=(
                        uuid.UUID(str(it["target_warehouse_id"]))
                        if it.get("target_warehouse_id")
                        else None
                    ),
                    uom=it.get("uom", "Nos"),
                )
                session.add(req_item)
            await session.flush()

        # Reload with items
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.mr_id == req.mr_id)
        )
        result = (await session.execute(stmt)).scalar_one()
        return result

    async def submit_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest:
        """Transitions material request from DRAFT to SUBMITTED."""
        req = await self.get_material_request(session, tenant_id, mr_id)
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status != "DRAFT":
            raise ValueError(f"Cannot submit request with status '{req.status}'. Must be DRAFT.")
        req.status = "SUBMITTED"
        await session.flush()
        return req

    async def cancel_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest:
        """Cancels a material request."""
        req = await self.get_material_request(session, tenant_id, mr_id)
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status in ("ORDERED", "CANCELLED"):
            raise ValueError(f"Cannot cancel request in status '{req.status}'.")
        req.status = "CANCELLED"
        await session.flush()
        return req

    async def get_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest | None:
        """Fetches material request with related items."""
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_material_requests(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
        material_request_type: str | None = None,
    ) -> list[MaterialRequest]:
        """Lists material requests for a tenant."""
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(MaterialRequest.status == status.upper())
        if material_request_type:
            stmt = stmt.where(MaterialRequest.material_request_type == material_request_type.upper())
        stmt = stmt.order_by(MaterialRequest.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def create_po_from_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
        supplier_id: uuid.UUID,
        po_number: str,
        items_to_order: list[dict[str, Any]] | None = None,
    ) -> PurchaseOrder:
        """Converts pending items in a submitted Material Request into a Purchase Order."""
        req = await self.get_material_request(session, tenant_id, mr_id)
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status not in ("SUBMITTED", "PARTIALLY_ORDERED"):
            raise ValueError(f"Material Request must be SUBMITTED or PARTIALLY_ORDERED, got {req.status}")

        req_items_by_id = {item.mr_item_id: item for item in req.items}
        po_lines: list[PurchaseOrderItem] = []
        total_subtotal = Decimal("0.0000")

        if not items_to_order:
            # Order all pending items
            items_to_order = []
            for item in req.items:
                remaining_qty = item.quantity - item.ordered_qty
                if remaining_qty > Decimal("0.0000"):
                    items_to_order.append({
                        "mr_item_id": item.mr_item_id,
                        "quantity": remaining_qty,
                    })

        if not items_to_order:
            raise ValueError("No eligible pending items to order in this Material Request.")

        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_number=po_number,
            supplier_id=supplier_id,
            order_date=date.today(),
            currency="USD",
            subtotal=Decimal("0.0000"),
            tax_amount=Decimal("0.0000"),
            total_amount=Decimal("0.0000"),
            status="SUBMITTED",
        )
        session.add(po)
        await session.flush()

        for ord_info in items_to_order:
            mr_item_id = (
                uuid.UUID(str(ord_info["mr_item_id"]))
                if isinstance(ord_info["mr_item_id"], str)
                else ord_info["mr_item_id"]
            )
            mr_item = req_items_by_id.get(mr_item_id)
            if not mr_item:
                raise ValueError(f"Line item {mr_item_id} not found in Material Request {mr_id}.")

            qty = Decimal(str(ord_info["quantity"]))
            remaining_qty = mr_item.quantity - mr_item.ordered_qty
            if qty > remaining_qty:
                raise ValueError(
                    f"Requested quantity {qty} exceeds pending quantity {remaining_qty} for item {mr_item.item.item_code}."
                )

            # Get price from item standard_rate or input
            unit_price = Decimal(str(ord_info.get("unit_price", mr_item.item.standard_rate or "0.0000")))
            line_total = qty * unit_price
            total_subtotal += line_total

            po_item = PurchaseOrderItem(
                tenant_id=tenant_id,
                po_id=po.po_id,
                item_id=mr_item.item_id,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
            session.add(po_item)
            mr_item.ordered_qty += qty

        po.subtotal = total_subtotal
        po.total_amount = total_subtotal

        # Check overall MR status
        all_ordered = all(it.ordered_qty >= it.quantity for it in req.items)
        req.status = "ORDERED" if all_ordered else "PARTIALLY_ORDERED"

        await session.flush()
        return po

    async def check_reorder_replenishment(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[MaterialRequest]:
        """Scans inventory levels vs reorder levels and creates Material Requests for depleted items."""
        # Find all purchase items with reorder_level > 0
        items_stmt = select(Item).where(
            Item.tenant_id == tenant_id,
            Item.is_purchase_item == True,
            Item.is_stock_item == True,
            Item.is_active == True,
            Item.reorder_level > Decimal("0.0000"),
        )
        items = (await session.execute(items_stmt)).scalars().all()

        created_mrs: list[MaterialRequest] = []
        depleted_lines: list[dict[str, Any]] = []

        for item in items:
            # Calculate total stock on hand across all warehouses
            stock_stmt = select(func.coalesce(func.sum(StockLevel.current_qty), 0)).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == item.item_id,
            )
            current_qty = Decimal(str((await session.execute(stock_stmt)).scalar() or 0))

            # If current stock is below or equal to reorder level
            if current_qty <= item.reorder_level:
                # Reorder quantity: target at least 2x reorder level or deficit
                deficit = (item.reorder_level * 2) - current_qty
                if deficit <= Decimal("0.0000"):
                    deficit = item.reorder_level

                depleted_lines.append({
                    "item_id": item.item_id,
                    "quantity": deficit,
                    "uom": item.stock_uom,
                })

        if depleted_lines:
            mr_number = f"MR-AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            mr = await self.create_material_request(
                session=session,
                tenant_id=tenant_id,
                mr_number=mr_number,
                material_request_type="PURCHASE",
                schedule_date=date.today() + timedelta(days=7),
                notes="Automated replenishment material request triggered by safety stock thresholds.",
                items=depleted_lines,
            )
            created_mrs.append(mr)

        return created_mrs


requisition_service = RequisitionService()
