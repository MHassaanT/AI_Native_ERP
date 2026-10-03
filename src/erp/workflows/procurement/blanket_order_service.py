"""Blanket Order (Contract Purchasing) Lifecycle and Drawdown Service."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.purchasing import (
    BlanketOrder,
    BlanketOrderItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)


class BlanketOrderService:
    """Core domain logic for Blanket Purchase Orders and Drawdown Releases."""

    async def create_blanket_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        order_number: str,
        supplier_id: uuid.UUID,
        from_date: date,
        to_date: date,
        items: list[dict[str, Any]],
    ) -> BlanketOrder:
        """Creates a long-term Blanket Order purchasing contract."""
        if from_date > to_date:
            raise ValueError(f"from_date ({from_date}) cannot be after to_date ({to_date}).")

        total_amount = Decimal("0.0000")

        bo = BlanketOrder(
            tenant_id=tenant_id,
            order_number=order_number,
            supplier_id=supplier_id,
            from_date=from_date,
            to_date=to_date,
            total_amount=Decimal("0.0000"),
            status="ACTIVE",
        )
        session.add(bo)
        await session.flush()

        for it in items:
            qty = Decimal(str(it["quantity"]))
            price = Decimal(str(it["unit_price"]))
            line_total = qty * price
            total_amount += line_total

            bo_item = BlanketOrderItem(
                tenant_id=tenant_id,
                blanket_order_id=bo.blanket_order_id,
                item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                quantity=qty,
                unit_price=price,
                ordered_qty=Decimal("0.0000"),
                line_total=line_total,
            )
            session.add(bo_item)

        bo.total_amount = total_amount
        await session.flush()

        return await self.get_blanket_order(session, tenant_id, bo.blanket_order_id)  # type: ignore

    async def get_blanket_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        blanket_order_id: uuid.UUID,
    ) -> BlanketOrder | None:
        """Fetches blanket order with items and supplier."""
        stmt = (
            select(BlanketOrder)
            .options(
                selectinload(BlanketOrder.items).selectinload(BlanketOrderItem.item),
                selectinload(BlanketOrder.supplier),
            )
            .where(
                BlanketOrder.tenant_id == tenant_id,
                BlanketOrder.blanket_order_id == blanket_order_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_blanket_orders(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[BlanketOrder]:
        """Lists blanket orders."""
        stmt = (
            select(BlanketOrder)
            .options(
                selectinload(BlanketOrder.items).selectinload(BlanketOrderItem.item),
                selectinload(BlanketOrder.supplier),
            )
            .where(BlanketOrder.tenant_id == tenant_id)
        )
        if supplier_id:
            stmt = stmt.where(BlanketOrder.supplier_id == supplier_id)
        if status:
            stmt = stmt.where(BlanketOrder.status == status.upper())
        stmt = stmt.order_by(BlanketOrder.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def create_po_from_blanket_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        blanket_order_id: uuid.UUID,
        po_number: str,
        item_drawdowns: list[dict[str, Any]],
        order_date: date | None = None,
    ) -> PurchaseOrder:
        """Draws down against a blanket order, locking in contract pricing and tracking quotas."""
        bo = await self.get_blanket_order(session, tenant_id, blanket_order_id)
        if not bo:
            raise ValueError(f"Blanket Order {blanket_order_id} not found.")

        if bo.status != "ACTIVE":
            raise ValueError(f"Blanket order status is '{bo.status}'. Only ACTIVE contracts can be drawn down.")

        today = order_date or date.today()
        if today < bo.from_date or today > bo.to_date:
            raise ValueError(
                f"Order date {today} is outside active contract validity period ({bo.from_date} to {bo.to_date})."
            )

        items_by_id = {item.item_id: item for item in bo.items}
        validated_items = []
        po_subtotal = Decimal("0.0000")

        for d in item_drawdowns:
            item_id = uuid.UUID(str(d["item_id"])) if isinstance(d["item_id"], str) else d["item_id"]
            bo_item = items_by_id.get(item_id)
            if not bo_item:
                raise ValueError(f"Item {item_id} is not part of Blanket Order {bo.order_number}.")

            drawdown_qty = Decimal(str(d["quantity"]))
            if drawdown_qty <= Decimal("0.0000"):
                raise ValueError(f"Drawdown quantity must be positive, got {drawdown_qty}.")

            remaining_qty = bo_item.quantity - bo_item.ordered_qty
            if drawdown_qty > remaining_qty:
                raise ValueError(
                    f"Drawdown quantity {drawdown_qty} exceeds remaining contract balance {remaining_qty} "
                    f"for item {bo_item.item.item_code}."
                )

            line_total = drawdown_qty * bo_item.unit_price
            po_subtotal += line_total
            validated_items.append((bo_item, item_id, drawdown_qty, bo_item.unit_price, line_total))

        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_number=po_number,
            supplier_id=bo.supplier_id,
            order_date=today,
            currency="USD",
            subtotal=po_subtotal,
            tax_amount=Decimal("0.0000"),
            total_amount=po_subtotal,
            status="SUBMITTED",
        )
        session.add(po)
        await session.flush()

        for bo_item, item_id, drawdown_qty, unit_price, line_total in validated_items:
            po_item = PurchaseOrderItem(
                tenant_id=tenant_id,
                po_id=po.po_id,
                item_id=item_id,
                quantity=drawdown_qty,
                unit_price=unit_price,
                line_total=line_total,
            )
            session.add(po_item)
            bo_item.ordered_qty += drawdown_qty

        po.subtotal = po_subtotal
        po.total_amount = po_subtotal

        # If all contracted quantities are drawn down, mark blanket order as CLOSED
        all_completed = all(it.ordered_qty >= it.quantity for it in bo.items)
        if all_completed:
            bo.status = "CLOSED"

        await session.flush()

        # Reload PO
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item),
                selectinload(PurchaseOrder.supplier),
            )
            .where(PurchaseOrder.po_id == po.po_id)
        )
        return (await session.execute(stmt)).scalar_one()


blanket_order_service = BlanketOrderService()
