"""Stock Reservation Service: Order-level inventory allocation locks."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import StockLevel, StockReservationEntry


class StockReservationService:
    """Core domain logic for locking inventory against Sales Orders and Material Demands."""

    async def create_reservation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        voucher_type: str,
        voucher_id: uuid.UUID,
        reserved_qty: Decimal,
        voucher_item_id: uuid.UUID | None = None,
    ) -> StockReservationEntry:
        """Locks inventory stock against a voucher so other orders cannot allocate it."""
        stmt = select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_id,
            StockLevel.warehouse_id == warehouse_id,
        )
        level = (await session.execute(stmt)).scalar_one_or_none()
        if not level:
            raise ValueError(f"No stock record found for item {item_id} in warehouse {warehouse_id}.")

        available = level.current_qty - level.reserved_qty
        if available < reserved_qty:
            raise ValueError(
                f"Insufficient unreserved stock to reserve. On-hand: {level.current_qty}, Reserved: {level.reserved_qty}, Available: {available}, Requested: {reserved_qty}"
            )

        # Update StockLevel
        level.reserved_qty += reserved_qty
        level.available_qty = level.current_qty - level.reserved_qty

        reservation = StockReservationEntry(
            tenant_id=tenant_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            voucher_type=voucher_type.upper(),
            voucher_id=voucher_id,
            voucher_item_id=voucher_item_id,
            reserved_qty=reserved_qty,
            consumed_qty=Decimal("0.0000"),
            status="ACTIVE",
        )
        session.add(reservation)
        await session.flush()
        return reservation

    async def consume_reservation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        reservation_id: uuid.UUID,
        qty_to_consume: Decimal,
    ) -> StockReservationEntry:
        """Fulfills a reservation, deducting from reserved_qty upon delivery or issuance."""
        stmt = select(StockReservationEntry).where(
            StockReservationEntry.tenant_id == tenant_id,
            StockReservationEntry.reservation_id == reservation_id,
        )
        res = (await session.execute(stmt)).scalar_one_or_none()
        if not res:
            raise ValueError(f"Reservation {reservation_id} not found.")
        if res.status != "ACTIVE":
            raise ValueError(f"Cannot consume reservation in status '{res.status}'.")

        res.consumed_qty += qty_to_consume

        # Release from StockLevel reserved_qty
        stmt_lvl = select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == res.item_id,
            StockLevel.warehouse_id == res.warehouse_id,
        )
        level = (await session.execute(stmt_lvl)).scalar_one_or_none()
        if level:
            level.reserved_qty = max(Decimal("0.0000"), level.reserved_qty - qty_to_consume)
            level.available_qty = level.current_qty - level.reserved_qty

        if res.consumed_qty >= res.reserved_qty:
            res.status = "FULFILLED"

        await session.flush()
        return res

    async def cancel_reservation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> StockReservationEntry:
        """Cancels an active reservation, unlocking reserved stock back to available stock."""
        stmt = select(StockReservationEntry).where(
            StockReservationEntry.tenant_id == tenant_id,
            StockReservationEntry.reservation_id == reservation_id,
        )
        res = (await session.execute(stmt)).scalar_one_or_none()
        if not res:
            raise ValueError(f"Reservation {reservation_id} not found.")
        if res.status != "ACTIVE":
            raise ValueError(f"Cannot cancel reservation in status '{res.status}'.")

        unconsumed = res.reserved_qty - res.consumed_qty

        stmt_lvl = select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == res.item_id,
            StockLevel.warehouse_id == res.warehouse_id,
        )
        level = (await session.execute(stmt_lvl)).scalar_one_or_none()
        if level:
            level.reserved_qty = max(Decimal("0.0000"), level.reserved_qty - unconsumed)
            level.available_qty = level.current_qty - level.reserved_qty

        res.status = "CANCELLED"
        await session.flush()
        return res

    async def list_reservations(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[StockReservationEntry]:
        """Lists stock reservations."""
        stmt = (
            select(StockReservationEntry)
            .options(
                selectinload(StockReservationEntry.item),
                selectinload(StockReservationEntry.warehouse),
            )
            .where(StockReservationEntry.tenant_id == tenant_id)
        )
        if item_id:
            stmt = stmt.where(StockReservationEntry.item_id == item_id)
        if warehouse_id:
            stmt = stmt.where(StockReservationEntry.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(StockReservationEntry.status == status.upper())
        stmt = stmt.order_by(StockReservationEntry.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


stock_reservation_service = StockReservationService()
