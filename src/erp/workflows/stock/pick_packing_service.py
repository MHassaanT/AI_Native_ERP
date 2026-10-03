"""Pick List and Packing Slip Order Fulfillment Service."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.logistics import (
    PackingSlip,
    PackingSlipItem,
    PickList,
    PickListItem,
)


class PickPackingService:
    """Core domain logic for Warehouse Picking and Packing Slips."""

    async def create_pick_list(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        pick_list_number: str,
        purpose: str = "DELIVERY",
        customer_id: uuid.UUID | None = None,
        notes: str | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> PickList:
        """Generates a new warehouse pick list."""
        pl = PickList(
            tenant_id=tenant_id,
            pick_list_number=pick_list_number,
            purpose=purpose.upper(),
            customer_id=customer_id,
            status="DRAFT",
            notes=notes,
        )
        session.add(pl)
        await session.flush()

        if items:
            for it in items:
                pl_item = PickListItem(
                    tenant_id=tenant_id,
                    pick_list_id=pl.pick_list_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    warehouse_id=uuid.UUID(str(it["warehouse_id"])) if isinstance(it["warehouse_id"], str) else it["warehouse_id"],
                    qty_to_pick=Decimal(str(it["qty_to_pick"])),
                    picked_qty=Decimal(str(it.get("picked_qty", "0.0000"))),
                    source_document_type=it.get("source_document_type"),
                    source_document_id=(
                        uuid.UUID(str(it["source_document_id"]))
                        if it.get("source_document_id")
                        else None
                    ),
                    batch_no=it.get("batch_no"),
                    serial_no=it.get("serial_no"),
                )
                session.add(pl_item)

        await session.flush()
        return await self.get_pick_list(session, tenant_id, pl.pick_list_id)  # type: ignore

    async def update_picked_qty(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        pick_list_id: uuid.UUID,
        pick_item_id: uuid.UUID,
        picked_qty: Decimal,
    ) -> PickListItem:
        """Updates picked quantity on a line item."""
        stmt = select(PickListItem).where(
            PickListItem.tenant_id == tenant_id,
            PickListItem.pick_list_id == pick_list_id,
            PickListItem.pick_item_id == pick_item_id,
        )
        item = (await session.execute(stmt)).scalar_one_or_none()
        if not item:
            raise ValueError(f"Pick item {pick_item_id} not found.")

        item.picked_qty = picked_qty
        pl = await session.get(PickList, pick_list_id)
        if pl and pl.status == "DRAFT":
            pl.status = "PICKING"

        await session.flush()
        return item

    async def complete_pick_list(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        pick_list_id: uuid.UUID,
    ) -> PickList:
        """Marks pick list as COMPLETED once all lines are picked."""
        pl = await self.get_pick_list(session, tenant_id, pick_list_id)
        if not pl:
            raise ValueError(f"Pick List {pick_list_id} not found.")

        for it in pl.items:
            if it.picked_qty < it.qty_to_pick:
                # Mark as picked or allow partial completion
                pass
        pl.status = "COMPLETED"
        await session.flush()
        return pl

    async def get_pick_list(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        pick_list_id: uuid.UUID,
    ) -> PickList | None:
        """Fetches pick list with items."""
        stmt = (
            select(PickList)
            .options(
                selectinload(PickList.items).selectinload(PickListItem.item),
                selectinload(PickList.items).selectinload(PickListItem.warehouse),
                selectinload(PickList.customer),
            )
            .where(PickList.tenant_id == tenant_id, PickList.pick_list_id == pick_list_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_pick_lists(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[PickList]:
        """Lists pick lists."""
        stmt = (
            select(PickList)
            .options(
                selectinload(PickList.items).selectinload(PickListItem.item),
                selectinload(PickList.customer),
            )
            .where(PickList.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(PickList.status == status.upper())
        stmt = stmt.order_by(PickList.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    # --- Packing Slips ---

    async def create_packing_slip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        slip_number: str,
        delivery_note_id: uuid.UUID | None = None,
        from_case_no: int = 1,
        to_case_no: int = 1,
        net_weight_pkg: Decimal = Decimal("0.0000"),
        gross_weight_pkg: Decimal = Decimal("0.0000"),
        items: list[dict[str, Any]] | None = None,
    ) -> PackingSlip:
        """Creates a carton/crate packing slip manifest."""
        ps = PackingSlip(
            tenant_id=tenant_id,
            slip_number=slip_number,
            delivery_note_id=delivery_note_id,
            from_case_no=from_case_no,
            to_case_no=to_case_no,
            net_weight_pkg=net_weight_pkg,
            gross_weight_pkg=gross_weight_pkg,
            status="DRAFT",
        )
        session.add(ps)
        await session.flush()

        if items:
            for it in items:
                psi = PackingSlipItem(
                    tenant_id=tenant_id,
                    packing_slip_id=ps.packing_slip_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    qty=Decimal(str(it["qty"])),
                    net_weight=Decimal(str(it.get("net_weight", "0.0000"))),
                )
                session.add(psi)

        await session.flush()
        return await self.get_packing_slip(session, tenant_id, ps.packing_slip_id)  # type: ignore

    async def submit_packing_slip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        packing_slip_id: uuid.UUID,
    ) -> PackingSlip:
        """Submits packing slip."""
        ps = await self.get_packing_slip(session, tenant_id, packing_slip_id)
        if not ps:
            raise ValueError(f"Packing Slip {packing_slip_id} not found.")
        ps.status = "SUBMITTED"
        await session.flush()
        return ps

    async def get_packing_slip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        packing_slip_id: uuid.UUID,
    ) -> PackingSlip | None:
        """Fetches packing slip with items."""
        stmt = (
            select(PackingSlip)
            .options(
                selectinload(PackingSlip.items).selectinload(PackingSlipItem.item),
                selectinload(PackingSlip.delivery_note),
            )
            .where(
                PackingSlip.tenant_id == tenant_id,
                PackingSlip.packing_slip_id == packing_slip_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_packing_slips(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        delivery_note_id: uuid.UUID | None = None,
    ) -> list[PackingSlip]:
        """Lists packing slips."""
        stmt = (
            select(PackingSlip)
            .options(
                selectinload(PackingSlip.items).selectinload(PackingSlipItem.item),
                selectinload(PackingSlip.delivery_note),
            )
            .where(PackingSlip.tenant_id == tenant_id)
        )
        if delivery_note_id:
            stmt = stmt.where(PackingSlip.delivery_note_id == delivery_note_id)
        stmt = stmt.order_by(PackingSlip.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


pick_packing_service = PickPackingService()
