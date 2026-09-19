"""Available-to-Promise (ATP) Calculator (PRD §Quotation Generation)."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item, StockLevel

logger = logging.getLogger(__name__)


class ATPResult(BaseModel):
    item_code: str
    requested_quantity: Decimal
    stock_on_hand: Decimal
    immediate_promise: bool
    requires_production_run: bool
    estimated_production_hours: float
    promised_delivery_date: date
    confidence_score: float = 0.98


class ATPCalculator:
    """Calculates realistic customer delivery commitment dates based on stock and shop-floor capacity."""

    async def calculate_atp(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        requested_quantity: Decimal,
        daily_capacity_units: Decimal = Decimal("100.00"),
    ) -> ATPResult:
        """Determines promise date using current inventory and production throughput."""
        # 1. Fetch Item
        item = (
            await session.execute(
                select(Item).where(Item.tenant_id == tenant_id, Item.item_id == item_id)
            )
        ).scalar_one_or_none()
        if not item:
            raise ValueError(f"Item '{item_id}' not found.")

        # 2. Check Available Stock on Hand
        stock_stmt = select(func.sum(StockLevel.available_qty)).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_id,
        )
        on_hand = (await session.execute(stock_stmt)).scalar() or Decimal("0.0000")

        today = date.today()

        if on_hand >= requested_quantity:
            # Immediate dispatch (2 days buffer for picking and logistics)
            return ATPResult(
                item_code=item.item_code,
                requested_quantity=requested_quantity,
                stock_on_hand=on_hand,
                immediate_promise=True,
                requires_production_run=False,
                estimated_production_hours=0.0,
                promised_delivery_date=today + timedelta(days=2),
                confidence_score=0.99,
            )

        # Deficit requires scheduling a production run
        deficit = requested_quantity - on_hand
        production_days = max(1, int(float(deficit / daily_capacity_units)))
        production_hours = production_days * 8.0

        # Transit & QA buffer: 3 days + production days
        promised_date = today + timedelta(days=production_days + 3)

        return ATPResult(
            item_code=item.item_code,
            requested_quantity=requested_quantity,
            stock_on_hand=on_hand,
            immediate_promise=False,
            requires_production_run=True,
            estimated_production_hours=production_hours,
            promised_delivery_date=promised_date,
            confidence_score=0.98,
        )


atp_calculator = ATPCalculator()
