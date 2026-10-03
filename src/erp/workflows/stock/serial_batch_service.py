"""Serial Number and Batch Tracking Service."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Batch, Item, SerialNo, Warehouse


class SerialBatchService:
    """Core domain logic for Serial Numbers and Batch tracking."""

    async def create_batch(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        batch_number: str,
        item_id: uuid.UUID,
        manufacturing_date: date | None = None,
        expiry_date: date | None = None,
        description: str | None = None,
    ) -> Batch:
        """Registers a new production or procurement lot/batch."""
        item = await session.get(Item, item_id)
        if not item or item.tenant_id != tenant_id:
            raise ValueError(f"Item {item_id} not found.")

        # Flag item as batch tracked if not already
        if not item.has_batch_no:
            item.has_batch_no = True

        status = "ACTIVE"
        if expiry_date and expiry_date < date.today():
            status = "EXPIRED"

        batch = Batch(
            tenant_id=tenant_id,
            batch_number=batch_number,
            item_id=item_id,
            manufacturing_date=manufacturing_date or date.today(),
            expiry_date=expiry_date,
            status=status,
            description=description,
        )
        session.add(batch)
        await session.flush()
        return batch

    async def list_batches(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Batch]:
        """Lists batches with item details."""
        stmt = (
            select(Batch)
            .options(selectinload(Batch.item))
            .where(Batch.tenant_id == tenant_id)
        )
        if item_id:
            stmt = stmt.where(Batch.item_id == item_id)
        if status:
            stmt = stmt.where(Batch.status == status.upper())
        stmt = stmt.order_by(Batch.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def create_serial_number(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        serial_number: str,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
        warranty_expiry_date: date | None = None,
        purchase_document_type: str | None = None,
        purchase_document_id: uuid.UUID | None = None,
    ) -> SerialNo:
        """Registers an individual unit serial number."""
        item = await session.get(Item, item_id)
        if not item or item.tenant_id != tenant_id:
            raise ValueError(f"Item {item_id} not found.")

        if not item.has_serial_no:
            item.has_serial_no = True

        serial = SerialNo(
            tenant_id=tenant_id,
            serial_number=serial_number.strip().upper(),
            item_id=item_id,
            warehouse_id=warehouse_id,
            status="ACTIVE" if warehouse_id else "AVAILABLE",
            purchase_document_type=purchase_document_type,
            purchase_document_id=purchase_document_id,
            warranty_expiry_date=warranty_expiry_date,
        )
        session.add(serial)
        await session.flush()
        return serial

    async def list_serial_numbers(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[SerialNo]:
        """Lists serial numbers."""
        stmt = (
            select(SerialNo)
            .options(selectinload(SerialNo.item), selectinload(SerialNo.warehouse))
            .where(SerialNo.tenant_id == tenant_id)
        )
        if item_id:
            stmt = stmt.where(SerialNo.item_id == item_id)
        if warehouse_id:
            stmt = stmt.where(SerialNo.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(SerialNo.status == status.upper())
        stmt = stmt.order_by(SerialNo.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def update_serial_status(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        serial_number: str,
        new_status: str,
        warehouse_id: uuid.UUID | None = None,
        delivery_document_type: str | None = None,
        delivery_document_id: uuid.UUID | None = None,
    ) -> SerialNo:
        """Transitions serial unit lifecycle status (e.g. ACTIVE -> DELIVERED)."""
        stmt = select(SerialNo).where(
            SerialNo.tenant_id == tenant_id,
            SerialNo.serial_number == serial_number.strip().upper(),
        )
        serial = (await session.execute(stmt)).scalar_one_or_none()
        if not serial:
            raise ValueError(f"Serial Number '{serial_number}' not found.")

        serial.status = new_status.upper()
        if warehouse_id is not None:
            serial.warehouse_id = warehouse_id
        if delivery_document_type:
            serial.delivery_document_type = delivery_document_type
        if delivery_document_id:
            serial.delivery_document_id = delivery_document_id

        await session.flush()
        return serial


serial_batch_service = SerialBatchService()
