"""Stock Entry Service: Universal inventory movements (Receipt, Issue, Transfer) with GL integration."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import (
    Item,
    SerialNo,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockLevel,
    Warehouse,
)
from erp.db.models.ledger import GeneralLedgerEntry


class StockEntryService:
    """Core domain logic for Stock Entries (Universal material movements)."""

    async def create_stock_entry(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entry_number: str,
        stock_entry_type: str = "MATERIAL_TRANSFER",
        posting_date: date | None = None,
        posting_time: time | None = None,
        purpose: str | None = None,
        from_warehouse_id: uuid.UUID | None = None,
        to_warehouse_id: uuid.UUID | None = None,
        notes: str | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> StockEntry:
        """Creates a new draft Stock Entry voucher."""
        if not posting_date:
            posting_date = date.today()
        if not posting_time:
            posting_time = datetime.now().time()

        entry_type = stock_entry_type.upper()
        if entry_type not in (
            "MATERIAL_RECEIPT",
            "MATERIAL_ISSUE",
            "MATERIAL_TRANSFER",
            "MANUFACTURE",
            "REPACK",
        ):
            raise ValueError(f"Invalid stock entry type: {stock_entry_type}")

        entry = StockEntry(
            tenant_id=tenant_id,
            entry_number=entry_number,
            stock_entry_type=entry_type,
            posting_date=posting_date,
            posting_time=posting_time,
            purpose=purpose,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            total_amount=Decimal("0.0000"),
            status="DRAFT",
            notes=notes,
        )
        session.add(entry)
        await session.flush()

        total_amount = Decimal("0.0000")
        if items:
            for it in items:
                qty = Decimal(str(it["qty"]))
                basic_rate = Decimal(str(it.get("basic_rate", "0.0000")))
                amount = qty * basic_rate
                total_amount += amount

                s_wh = it.get("s_warehouse_id", from_warehouse_id)
                t_wh = it.get("t_warehouse_id", to_warehouse_id)

                entry_item = StockEntryItem(
                    tenant_id=tenant_id,
                    entry_id=entry.entry_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    s_warehouse_id=uuid.UUID(str(s_wh)) if s_wh else None,
                    t_warehouse_id=uuid.UUID(str(t_wh)) if t_wh else None,
                    qty=qty,
                    uom=it.get("uom", "Nos"),
                    basic_rate=basic_rate,
                    amount=amount,
                    batch_no=it.get("batch_no"),
                    serial_no=it.get("serial_no"),
                )
                session.add(entry_item)

        entry.total_amount = total_amount
        await session.flush()

        return await self.get_stock_entry(session, tenant_id, entry.entry_id)  # type: ignore

    async def submit_stock_entry(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> StockEntry:
        """Submits Stock Entry, writes immutable StockLedgerEntries, updates StockLevels, and posts GL."""
        entry = await self.get_stock_entry(session, tenant_id, entry_id)
        if not entry:
            raise ValueError(f"Stock Entry {entry_id} not found.")
        if entry.status != "DRAFT":
            raise ValueError(f"Cannot submit Stock Entry in status '{entry.status}'.")

        posting_dt = datetime.combine(entry.posting_date, entry.posting_time)

        for item_line in entry.items:
            qty = item_line.qty
            rate = item_line.basic_rate
            item_id = item_line.item_id

            if entry.stock_entry_type == "MATERIAL_RECEIPT":
                if not item_line.t_warehouse_id:
                    raise ValueError(f"Target warehouse required for Receipt on item {item_id}.")
                # 1. Update/Create StockLevel in target warehouse
                stock_level = await self._get_or_create_stock_level(
                    session, tenant_id, item_id, item_line.t_warehouse_id
                )
                prev_qty = stock_level.current_qty
                new_qty = prev_qty + qty
                new_valuation = (
                    ((prev_qty * stock_level.valuation_rate) + (qty * rate)) / new_qty
                    if new_qty > 0
                    else rate
                )

                stock_level.current_qty = new_qty
                stock_level.available_qty = new_qty - stock_level.reserved_qty
                stock_level.valuation_rate = new_valuation

                # 2. Write StockLedgerEntry
                sle = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=posting_dt,
                    item_id=item_id,
                    warehouse_id=item_line.t_warehouse_id,
                    actual_qty=qty,
                    qty_after_transaction=new_qty,
                    incoming_rate=rate,
                    outgoing_rate=Decimal("0.0000"),
                    valuation_rate=new_valuation,
                    stock_value_difference=qty * rate,
                    source_document_type="STOCK_ENTRY",
                    source_document_id=entry.entry_id,
                    lot_number=item_line.batch_no,
                    serial_no=item_line.serial_no,
                )
                session.add(sle)

                # 3. Post General Ledger (Stock in Hand vs Stock Adjustment)
                val_diff = qty * rate
                if val_diff > Decimal("0.0000"):
                    tx_id = uuid.uuid4()
                    f_year = entry.posting_date.year
                    f_period = entry.posting_date.month
                    session.add(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=entry.posting_date,
                            fiscal_year=f_year,
                            fiscal_period=f_period,
                            account_code="1300-STOCK-IN-HAND",
                            cost_center="DEFAULT",
                            debit_amount=val_diff,
                            credit_amount=Decimal("0.0000"),
                            currency="USD",
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="STOCK_ENTRY",
                            source_document_id=entry.entry_id,
                        )
                    )
                    session.add(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=entry.posting_date,
                            fiscal_year=f_year,
                            fiscal_period=f_period,
                            account_code="5200-STOCK-ADJUSTMENT",
                            cost_center="DEFAULT",
                            debit_amount=Decimal("0.0000"),
                            credit_amount=val_diff,
                            currency="USD",
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="STOCK_ENTRY",
                            source_document_id=entry.entry_id,
                        )
                    )

            elif entry.stock_entry_type == "MATERIAL_ISSUE":
                if not item_line.s_warehouse_id:
                    raise ValueError(f"Source warehouse required for Issue on item {item_id}.")
                stock_level = await self._get_or_create_stock_level(
                    session, tenant_id, item_id, item_line.s_warehouse_id
                )
                if stock_level.current_qty < qty:
                    raise ValueError(
                        f"Insufficient stock for item {item_id} in source warehouse. Available: {stock_level.current_qty}, Requested: {qty}"
                    )

                new_qty = stock_level.current_qty - qty
                stock_level.current_qty = new_qty
                stock_level.available_qty = new_qty - stock_level.reserved_qty

                # Use current valuation rate if basic_rate not specified
                effective_rate = rate if rate > Decimal("0.0000") else stock_level.valuation_rate
                val_diff = qty * effective_rate

                sle = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=posting_dt,
                    item_id=item_id,
                    warehouse_id=item_line.s_warehouse_id,
                    actual_qty=-qty,
                    qty_after_transaction=new_qty,
                    incoming_rate=Decimal("0.0000"),
                    outgoing_rate=effective_rate,
                    valuation_rate=stock_level.valuation_rate,
                    stock_value_difference=-val_diff,
                    source_document_type="STOCK_ENTRY",
                    source_document_id=entry.entry_id,
                    lot_number=item_line.batch_no,
                    serial_no=item_line.serial_no,
                )
                session.add(sle)

                # Post GL (Stock Adjustment Expense Debit vs Stock In Hand Credit)
                if val_diff > Decimal("0.0000"):
                    tx_id = uuid.uuid4()
                    f_year = entry.posting_date.year
                    f_period = entry.posting_date.month
                    session.add(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=entry.posting_date,
                            fiscal_year=f_year,
                            fiscal_period=f_period,
                            account_code="5200-STOCK-ADJUSTMENT",
                            cost_center="DEFAULT",
                            debit_amount=val_diff,
                            credit_amount=Decimal("0.0000"),
                            currency="USD",
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="STOCK_ENTRY",
                            source_document_id=entry.entry_id,
                        )
                    )
                    session.add(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=entry.posting_date,
                            fiscal_year=f_year,
                            fiscal_period=f_period,
                            account_code="1300-STOCK-IN-HAND",
                            cost_center="DEFAULT",
                            debit_amount=Decimal("0.0000"),
                            credit_amount=val_diff,
                            currency="USD",
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="STOCK_ENTRY",
                            source_document_id=entry.entry_id,
                        )
                    )

            elif entry.stock_entry_type == "MATERIAL_TRANSFER":
                if not item_line.s_warehouse_id or not item_line.t_warehouse_id:
                    raise ValueError(
                        f"Both source and target warehouses required for Transfer on item {item_id}."
                    )
                # 1. Deduct from source
                s_level = await self._get_or_create_stock_level(
                    session, tenant_id, item_id, item_line.s_warehouse_id
                )
                if s_level.current_qty < qty:
                    raise ValueError(
                        f"Insufficient stock for transfer in source warehouse. Available: {s_level.current_qty}, Requested: {qty}"
                    )
                new_s_qty = s_level.current_qty - qty
                s_level.current_qty = new_s_qty
                s_level.available_qty = new_s_qty - s_level.reserved_qty

                transfer_rate = rate if rate > Decimal("0.0000") else s_level.valuation_rate

                sle_out = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=posting_dt,
                    item_id=item_id,
                    warehouse_id=item_line.s_warehouse_id,
                    actual_qty=-qty,
                    qty_after_transaction=new_s_qty,
                    incoming_rate=Decimal("0.0000"),
                    outgoing_rate=transfer_rate,
                    valuation_rate=s_level.valuation_rate,
                    stock_value_difference=-(qty * transfer_rate),
                    source_document_type="STOCK_ENTRY",
                    source_document_id=entry.entry_id,
                    lot_number=item_line.batch_no,
                    serial_no=item_line.serial_no,
                )
                session.add(sle_out)

                # 2. Add to target
                t_level = await self._get_or_create_stock_level(
                    session, tenant_id, item_id, item_line.t_warehouse_id
                )
                prev_t_qty = t_level.current_qty
                new_t_qty = prev_t_qty + qty
                new_t_valuation = (
                    ((prev_t_qty * t_level.valuation_rate) + (qty * transfer_rate)) / new_t_qty
                    if new_t_qty > 0
                    else transfer_rate
                )
                t_level.current_qty = new_t_qty
                t_level.available_qty = new_t_qty - t_level.reserved_qty
                t_level.valuation_rate = new_t_valuation

                sle_in = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=posting_dt,
                    item_id=item_id,
                    warehouse_id=item_line.t_warehouse_id,
                    actual_qty=qty,
                    qty_after_transaction=new_t_qty,
                    incoming_rate=transfer_rate,
                    outgoing_rate=Decimal("0.0000"),
                    valuation_rate=new_t_valuation,
                    stock_value_difference=qty * transfer_rate,
                    source_document_type="STOCK_ENTRY",
                    source_document_id=entry.entry_id,
                    lot_number=item_line.batch_no,
                    serial_no=item_line.serial_no,
                )
                session.add(sle_in)

            elif entry.stock_entry_type in ("MANUFACTURE", "REPACK"):
                # Handle dual-flow manufacture: consumption lines (source wh) vs finished production lines (target wh)
                if item_line.s_warehouse_id and not item_line.t_warehouse_id:
                    # Consumption leg from WIP warehouse
                    s_level = await self._get_or_create_stock_level(
                        session, tenant_id, item_id, item_line.s_warehouse_id
                    )
                    new_s_qty = s_level.current_qty - qty
                    s_level.current_qty = new_s_qty
                    s_level.available_qty = new_s_qty - s_level.reserved_qty
                    effective_rate = rate if rate > Decimal("0.0000") else s_level.valuation_rate

                    sle_out = StockLedgerEntry(
                        tenant_id=tenant_id,
                        posting_datetime=posting_dt,
                        item_id=item_id,
                        warehouse_id=item_line.s_warehouse_id,
                        actual_qty=-qty,
                        qty_after_transaction=new_s_qty,
                        incoming_rate=Decimal("0.0000"),
                        outgoing_rate=effective_rate,
                        valuation_rate=s_level.valuation_rate,
                        stock_value_difference=-(qty * effective_rate),
                        source_document_type="STOCK_ENTRY",
                        source_document_id=entry.entry_id,
                        lot_number=item_line.batch_no,
                        serial_no=item_line.serial_no,
                    )
                    session.add(sle_out)

                elif item_line.t_warehouse_id and not item_line.s_warehouse_id:
                    # Finished good receipt into FG warehouse
                    t_level = await self._get_or_create_stock_level(
                        session, tenant_id, item_id, item_line.t_warehouse_id
                    )
                    prev_t_qty = t_level.current_qty
                    new_t_qty = prev_t_qty + qty
                    new_t_valuation = (
                        ((prev_t_qty * t_level.valuation_rate) + (qty * rate)) / new_t_qty
                        if new_t_qty > 0
                        else rate
                    )
                    t_level.current_qty = new_t_qty
                    t_level.available_qty = new_t_qty - t_level.reserved_qty
                    t_level.valuation_rate = new_t_valuation

                    sle_in = StockLedgerEntry(
                        tenant_id=tenant_id,
                        posting_datetime=posting_dt,
                        item_id=item_id,
                        warehouse_id=item_line.t_warehouse_id,
                        actual_qty=qty,
                        qty_after_transaction=new_t_qty,
                        incoming_rate=rate,
                        outgoing_rate=Decimal("0.0000"),
                        valuation_rate=new_t_valuation,
                        stock_value_difference=qty * rate,
                        source_document_type="STOCK_ENTRY",
                        source_document_id=entry.entry_id,
                        lot_number=item_line.batch_no,
                        serial_no=item_line.serial_no,
                    )
                    session.add(sle_in)

            # Update Serial Number location if serial_no present
            if item_line.serial_no:
                stmt = select(SerialNo).where(
                    SerialNo.tenant_id == tenant_id,
                    SerialNo.serial_number == item_line.serial_no,
                )
                ser = (await session.execute(stmt)).scalar_one_or_none()
                if ser:
                    if entry.stock_entry_type in ("MATERIAL_RECEIPT", "MATERIAL_TRANSFER"):
                        ser.warehouse_id = item_line.t_warehouse_id
                        ser.status = "ACTIVE"
                    elif entry.stock_entry_type == "MATERIAL_ISSUE":
                        ser.warehouse_id = None
                        ser.status = "DELIVERED"

        entry.status = "SUBMITTED"
        await session.flush()
        return entry

    async def cancel_stock_entry(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> StockEntry:
        """Cancels a stock entry."""
        entry = await self.get_stock_entry(session, tenant_id, entry_id)
        if not entry:
            raise ValueError(f"Stock Entry {entry_id} not found.")
        if entry.status != "SUBMITTED":
            raise ValueError(f"Only SUBMITTED entries can be cancelled. Current: {entry.status}")
        entry.status = "CANCELLED"
        await session.flush()
        return entry

    async def get_stock_entry(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> StockEntry | None:
        """Fetches Stock Entry with loaded relationships."""
        stmt = (
            select(StockEntry)
            .options(
                selectinload(StockEntry.items).selectinload(StockEntryItem.item),
                selectinload(StockEntry.items).selectinload(StockEntryItem.source_warehouse),
                selectinload(StockEntry.items).selectinload(StockEntryItem.target_warehouse),
                selectinload(StockEntry.from_warehouse),
                selectinload(StockEntry.to_warehouse),
            )
            .where(StockEntry.tenant_id == tenant_id, StockEntry.entry_id == entry_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_stock_entries(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        stock_entry_type: str | None = None,
        status: str | None = None,
    ) -> list[StockEntry]:
        """Lists stock entries for tenant."""
        stmt = (
            select(StockEntry)
            .options(
                selectinload(StockEntry.items).selectinload(StockEntryItem.item),
                selectinload(StockEntry.from_warehouse),
                selectinload(StockEntry.to_warehouse),
            )
            .where(StockEntry.tenant_id == tenant_id)
        )
        if stock_entry_type:
            stmt = stmt.where(StockEntry.stock_entry_type == stock_entry_type.upper())
        if status:
            stmt = stmt.where(StockEntry.status == status.upper())
        stmt = stmt.order_by(StockEntry.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def _get_or_create_stock_level(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockLevel:
        stmt = select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_id,
            StockLevel.warehouse_id == warehouse_id,
        )
        level = (await session.execute(stmt)).scalar_one_or_none()
        if not level:
            level = StockLevel(
                tenant_id=tenant_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                current_qty=Decimal("0.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("0.0000"),
                valuation_rate=Decimal("0.0000"),
            )
            session.add(level)
            await session.flush()
        return level


stock_entry_service = StockEntryService()
