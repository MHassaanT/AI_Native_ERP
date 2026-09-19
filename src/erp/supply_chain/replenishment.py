"""Autonomous Replenishment Coordinator (PRD §Inventory Replenishment)."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item, StockLevel
from erp.db.models.purchasing import PurchaseOrder, PurchaseOrderItem, Supplier
from erp.events.outbox import OutboxManager
from erp.ledger.ceilings import evaluate_autonomy_tier
from erp.supply_chain.eoq_calculator import eoq_calculator
from erp.supply_chain.rop_engine import rop_engine

logger = logging.getLogger(__name__)


class ReplenishmentEvaluationResult(BaseModel):
    item_code: str
    current_on_hand: Decimal
    current_on_order: Decimal
    reorder_point: Decimal
    reorder_triggered: bool
    generated_po_number: str | None = None
    ordered_quantity: Decimal = Decimal("0.0000")
    total_order_value: Decimal = Decimal("0.0000")
    autonomy_tier: str | None = None


class ReplenishmentCoordinator:
    """Evaluates stock levels against dynamic ROP and dispatches automated purchase orders."""

    async def evaluate_and_replenish_item(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        daily_demand_mean: Decimal = Decimal("150.0000"),
        daily_demand_std: Decimal = Decimal("25.0000"),
        lead_time_mean_days: Decimal = Decimal("14.0000"),
        lead_time_std_days: Decimal = Decimal("3.0000"),
    ) -> ReplenishmentEvaluationResult:
        """Evaluates OnHand + OnOrder <= ROP and creates autonomous PO if triggered."""
        # 1. Fetch Item
        item = (
            await session.execute(
                select(Item).where(Item.tenant_id == tenant_id, Item.item_id == item_id)
            )
        ).scalar_one_or_none()
        if not item:
            raise ValueError(f"Item '{item_id}' not found.")

        # 2. Fetch On-Hand Stock
        stock_sum_stmt = select(func.sum(StockLevel.current_qty)).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_id,
        )
        on_hand = (await session.execute(stock_sum_stmt)).scalar() or Decimal("0.0000")

        # 3. Fetch On-Order Stock from open POs
        po_stmt = (
            select(func.sum(PurchaseOrderItem.quantity))
            .join(PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.po_id)
            .where(
                PurchaseOrderItem.tenant_id == tenant_id,
                PurchaseOrderItem.item_id == item_id,
                PurchaseOrder.status.in_(["SUBMITTED", "PARTIALLY_RECEIVED"]),
            )
        )
        on_order = (await session.execute(po_stmt)).scalar() or Decimal("0.0000")

        # 4. Calculate Dynamic ROP
        rop_eval = rop_engine.calculate_rop(
            item_code=item.item_code,
            mu_d=daily_demand_mean,
            sigma_d=daily_demand_std,
            mu_l=lead_time_mean_days,
            sigma_l=lead_time_std_days,
        )

        total_available = on_hand + on_order
        reorder_triggered = total_available <= rop_eval.reorder_point

        if not reorder_triggered:
            return ReplenishmentEvaluationResult(
                item_code=item.item_code,
                current_on_hand=on_hand,
                current_on_order=on_order,
                reorder_point=rop_eval.reorder_point,
                reorder_triggered=False,
            )

        # 5. Calculate EOQ Quantity
        annual_demand = daily_demand_mean * Decimal("365.0000")
        eoq_res = eoq_calculator.calculate_eoq(
            item_code=item.item_code,
            annual_demand=annual_demand,
        )
        order_qty = eoq_res.recommended_order_quantity
        unit_price = item.standard_rate or Decimal("2.4500")
        order_total = (order_qty * unit_price).quantize(Decimal("0.0001"))

        # 6. Verify autonomy ceiling
        tier_eval = evaluate_autonomy_tier(order_total, human_approved=False)

        # 7. Find preferred supplier
        sup_stmt = select(Supplier).where(Supplier.tenant_id == tenant_id).limit(1)
        supplier = (await session.execute(sup_stmt)).scalar_one_or_none()
        if not supplier:
            raise ValueError("No supplier configured for tenant replenishment.")

        # 8. Create Purchase Order
        po_number = f"PO-AUTO-{uuid.uuid4().hex[:6].upper()}"
        new_po = PurchaseOrder(
            tenant_id=tenant_id,
            po_number=po_number,
            supplier_id=supplier.supplier_id,
            order_date=date.today(),
            currency="USD",
            subtotal=order_total,
            tax_amount=Decimal("0.0000"),
            total_amount=order_total,
            status="SUBMITTED" if order_total <= Decimal("25000.0000") else "DRAFT",
        )
        session.add(new_po)
        await session.flush()

        po_item = PurchaseOrderItem(
            tenant_id=tenant_id,
            po_id=new_po.po_id,
            item_id=item.item_id,
            quantity=order_qty,
            unit_price=unit_price,
            line_total=order_total,
        )
        session.add(po_item)

        # 9. Write outbox event
        await OutboxManager.enqueue_event(
            session=session,
            tenant_id=tenant_id,
            aggregate_type="PURCHASE_ORDER",
            aggregate_id=str(new_po.po_id),
            event_type="erp.supplychain.reorder_triggered",
            payload={
                "po_number": po_number,
                "item_code": item.item_code,
                "ordered_quantity": str(order_qty),
                "total_value": str(order_total),
                "rop": str(rop_eval.reorder_point),
                "autonomy_tier": tier_eval.tier.value,
            },
        )

        await session.flush()
        logger.info(
            "Autonomous reorder triggered for %s: Created %s for %s units ($%s)",
            item.item_code,
            po_number,
            order_qty,
            order_total,
        )

        return ReplenishmentEvaluationResult(
            item_code=item.item_code,
            current_on_hand=on_hand,
            current_on_order=on_order,
            reorder_point=rop_eval.reorder_point,
            reorder_triggered=True,
            generated_po_number=po_number,
            ordered_quantity=order_qty,
            total_order_value=order_total,
            autonomy_tier=tier_eval.tier.value,
        )


replenishment_coordinator = ReplenishmentCoordinator()
