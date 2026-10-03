"""Subcontracting (Outside Processing & Component Issuance) Service."""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.subcontracting import (
    SubcontractingOrder,
    SubcontractingOrderItem,
    SubcontractingReceipt,
    SubcontractingReceiptItem,
    SubcontractingSuppliedItem,
)

logger = logging.getLogger(__name__)


class SubcontractingService:
    """Core domain logic for Subcontracting Orders, Component Transfers, and Finished Goods Receipts."""

    async def create_subcontracting_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sco_number: str,
        supplier_id: uuid.UUID,
        order_date: date | None = None,
        service_cost: Decimal = Decimal("0.0000"),
        po_id: uuid.UUID | None = None,
        notes: str | None = None,
        finished_items: list[dict[str, Any]] | None = None,
        supplied_items: list[dict[str, Any]] | None = None,
    ) -> SubcontractingOrder:
        """Creates a Subcontracting Order with finished good lines and raw component requirements."""
        if not order_date:
            order_date = date.today()

        sco = SubcontractingOrder(
            tenant_id=tenant_id,
            sco_number=sco_number,
            supplier_id=supplier_id,
            po_id=po_id,
            order_date=order_date,
            service_cost=service_cost,
            status="DRAFT",
            notes=notes,
        )
        session.add(sco)
        await session.flush()

        if finished_items:
            for it in finished_items:
                qty = Decimal(str(it["quantity"]))
                price = Decimal(str(it.get("unit_price", "0.0000")))
                line_total = qty * price
                item = SubcontractingOrderItem(
                    tenant_id=tenant_id,
                    sco_id=sco.sco_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    quantity=qty,
                    unit_price=price,
                    line_total=line_total,
                )
                session.add(item)

        if supplied_items:
            for s in supplied_items:
                req_qty = Decimal(str(s["required_qty"]))
                supplied_item = SubcontractingSuppliedItem(
                    tenant_id=tenant_id,
                    sco_id=sco.sco_id,
                    raw_item_id=uuid.UUID(str(s["raw_item_id"])) if isinstance(s["raw_item_id"], str) else s["raw_item_id"],
                    required_qty=req_qty,
                    supplied_qty=Decimal("0.0000"),
                    consumed_qty=Decimal("0.0000"),
                    source_warehouse_id=(
                        uuid.UUID(str(s["source_warehouse_id"])) if s.get("source_warehouse_id") else None
                    ),
                    supplier_warehouse_id=(
                        uuid.UUID(str(s["supplier_warehouse_id"])) if s.get("supplier_warehouse_id") else None
                    ),
                )
                session.add(supplied_item)

        await session.flush()
        return await self.get_subcontracting_order(session, tenant_id, sco.sco_id)  # type: ignore

    async def submit_subcontracting_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sco_id: uuid.UUID,
    ) -> SubcontractingOrder:
        """Transitions Subcontracting Order from DRAFT to SUBMITTED."""
        sco = await self.get_subcontracting_order(session, tenant_id, sco_id)
        if not sco:
            raise ValueError(f"Subcontracting Order {sco_id} not found.")
        if sco.status != "DRAFT":
            raise ValueError(f"Cannot submit subcontracting order in status '{sco.status}'.")
        sco.status = "SUBMITTED"
        await session.flush()
        return sco

    async def transfer_subcontracting_materials(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sco_id: uuid.UUID,
        transfers: list[dict[str, Any]],
    ) -> SubcontractingOrder:
        """Transfers raw materials from internal warehouse to subcontractor warehouse."""
        sco = await self.get_subcontracting_order(session, tenant_id, sco_id)
        if not sco:
            raise ValueError(f"Subcontracting Order {sco_id} not found.")

        if sco.status not in ("SUBMITTED", "IN_PROCESS"):
            raise ValueError(f"Subcontracting order must be SUBMITTED or IN_PROCESS, got '{sco.status}'.")

        supplied_map = {item.raw_item_id: item for item in sco.supplied_items}

        for tr in transfers:
            raw_item_id = uuid.UUID(str(tr["raw_item_id"])) if isinstance(tr["raw_item_id"], str) else tr["raw_item_id"]
            qty = Decimal(str(tr["quantity"]))
            src_wh = uuid.UUID(str(tr["source_warehouse_id"])) if isinstance(tr["source_warehouse_id"], str) else tr["source_warehouse_id"]
            supp_wh = uuid.UUID(str(tr["supplier_warehouse_id"])) if isinstance(tr["supplier_warehouse_id"], str) else tr["supplier_warehouse_id"]

            supplied_line = supplied_map.get(raw_item_id)
            if not supplied_line:
                raise ValueError(f"Raw material {raw_item_id} is not scheduled for subcontracting order {sco.sco_number}.")

            # 1. Deduct from source warehouse
            src_stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == raw_item_id,
                        StockLevel.warehouse_id == src_wh,
                    )
                )
            ).scalar_one_or_none()

            rate = Decimal("0.0000")
            if src_stk:
                src_stk.current_qty -= qty
                src_stk.available_qty = src_stk.current_qty - src_stk.reserved_qty
                rate = src_stk.valuation_rate
                qty_after_src = src_stk.current_qty
            else:
                src_stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=raw_item_id,
                    warehouse_id=src_wh,
                    current_qty=-qty,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=-qty,
                    valuation_rate=rate,
                )
                session.add(src_stk)
                qty_after_src = -qty

            session.add(
                StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.now(),
                    item_id=raw_item_id,
                    warehouse_id=src_wh,
                    actual_qty=-qty,
                    qty_after_transaction=qty_after_src,
                    outgoing_rate=rate,
                    valuation_rate=rate,
                    source_document_type="SUBCONTRACTING_TRANSFER_OUT",
                    source_document_id=sco.sco_id,
                )
            )

            # 2. Add to supplier warehouse
            supp_stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == raw_item_id,
                        StockLevel.warehouse_id == supp_wh,
                    )
                )
            ).scalar_one_or_none()

            if supp_stk:
                supp_stk.current_qty += qty
                supp_stk.available_qty = supp_stk.current_qty - supp_stk.reserved_qty
                supp_stk.valuation_rate = rate
                qty_after_supp = supp_stk.current_qty
            else:
                supp_stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=raw_item_id,
                    warehouse_id=supp_wh,
                    current_qty=qty,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=qty,
                    valuation_rate=rate,
                )
                session.add(supp_stk)
                qty_after_supp = qty

            session.add(
                StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.now(),
                    item_id=raw_item_id,
                    warehouse_id=supp_wh,
                    actual_qty=qty,
                    qty_after_transaction=qty_after_supp,
                    incoming_rate=rate,
                    valuation_rate=rate,
                    source_document_type="SUBCONTRACTING_TRANSFER_IN",
                    source_document_id=sco.sco_id,
                )
            )

            # Update supplied item tracking
            supplied_line.supplied_qty += qty
            supplied_line.source_warehouse_id = src_wh
            supplied_line.supplier_warehouse_id = supp_wh

        sco.status = "IN_PROCESS"
        await session.flush()
        return await self.get_subcontracting_order(session, tenant_id, sco.sco_id)  # type: ignore

    async def receive_subcontracting_receipt(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        scr_number: str,
        sco_id: uuid.UUID,
        target_warehouse_id: uuid.UUID,
        finished_items_received: list[dict[str, Any]],
        posting_date: date | None = None,
    ) -> SubcontractingReceipt:
        """Receives processed finished goods, consumes raw components, rolls up valuation, and posts GL entries."""
        sco = await self.get_subcontracting_order(session, tenant_id, sco_id)
        if not sco:
            raise ValueError(f"Subcontracting Order {sco_id} not found.")

        if not posting_date:
            posting_date = date.today()

        scr = SubcontractingReceipt(
            tenant_id=tenant_id,
            scr_number=scr_number,
            sco_id=sco.sco_id,
            supplier_id=sco.supplier_id,
            target_warehouse_id=target_warehouse_id,
            posting_date=posting_date,
            status="COMPLETED",
        )
        session.add(scr)
        await session.flush()

        # 1. Calculate component consumption and valuation
        total_ordered_fg = sum((item.quantity for item in sco.items), Decimal("0.0000"))
        total_rec_fg = sum((Decimal(str(it["quantity_received"])) for it in finished_items_received), Decimal("0.0000"))
        ratio = (total_rec_fg / total_ordered_fg) if total_ordered_fg > Decimal("0.0000") else Decimal("1.0000")

        total_component_cost = Decimal("0.0000")

        for supp_item in sco.supplied_items:
            consume_qty = (supp_item.required_qty * ratio).quantize(Decimal("0.0001"))
            supp_wh = supp_item.supplier_warehouse_id

            rate = Decimal("0.0000")
            if supp_wh:
                wh_stk = (
                    await session.execute(
                        select(StockLevel).where(
                            StockLevel.tenant_id == tenant_id,
                            StockLevel.item_id == supp_item.raw_item_id,
                            StockLevel.warehouse_id == supp_wh,
                        )
                    )
                ).scalar_one_or_none()

                if wh_stk:
                    wh_stk.current_qty -= consume_qty
                    wh_stk.available_qty = wh_stk.current_qty - wh_stk.reserved_qty
                    rate = wh_stk.valuation_rate
                    qty_after = wh_stk.current_qty
                else:
                    qty_after = -consume_qty

                comp_val = (consume_qty * rate).quantize(Decimal("0.0001"))
                total_component_cost += comp_val

                session.add(
                    StockLedgerEntry(
                        tenant_id=tenant_id,
                        posting_datetime=datetime.now(),
                        item_id=supp_item.raw_item_id,
                        warehouse_id=supp_wh,
                        actual_qty=-consume_qty,
                        qty_after_transaction=qty_after,
                        outgoing_rate=rate,
                        valuation_rate=rate,
                        source_document_type="SUBCONTRACTING_COMPONENT_CONSUME",
                        source_document_id=scr.scr_id,
                    )
                )

            supp_item.consumed_qty += consume_qty

        # 2. Ingest finished items with rolled-up valuation (Raw Material Cost + Service Fee)
        total_service_cost = sum(
            (Decimal(str(it["quantity_received"])) * Decimal(str(it.get("service_rate", "0.0000"))))
            for it in finished_items_received
        ).quantize(Decimal("0.0001"))

        total_fg_valuation = total_component_cost + total_service_cost

        for it in finished_items_received:
            fg_item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty_rec = Decimal(str(it["quantity_received"]))
            srv_rate = Decimal(str(it.get("service_rate", "0.0000")))

            scr_item = SubcontractingReceiptItem(
                tenant_id=tenant_id,
                scr_id=scr.scr_id,
                item_id=fg_item_id,
                quantity_received=qty_rec,
                service_rate=srv_rate,
            )
            session.add(scr_item)

            # Valuation rate per unit = Total FG Value / Total FG Qty
            unit_val_rate = (total_fg_valuation / total_rec_fg) if total_rec_fg > 0 else srv_rate

            fg_stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == fg_item_id,
                        StockLevel.warehouse_id == target_warehouse_id,
                    )
                )
            ).scalar_one_or_none()

            if fg_stk:
                fg_stk.current_qty += qty_rec
                fg_stk.available_qty = fg_stk.current_qty - fg_stk.reserved_qty
                if unit_val_rate > 0:
                    fg_stk.valuation_rate = unit_val_rate
                qty_after_fg = fg_stk.current_qty
                rate_fg = fg_stk.valuation_rate
            else:
                fg_stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=fg_item_id,
                    warehouse_id=target_warehouse_id,
                    current_qty=qty_rec,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=qty_rec,
                    valuation_rate=unit_val_rate,
                )
                session.add(fg_stk)
                qty_after_fg = qty_rec
                rate_fg = unit_val_rate

            session.add(
                StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.now(),
                    item_id=fg_item_id,
                    warehouse_id=target_warehouse_id,
                    actual_qty=qty_rec,
                    qty_after_transaction=qty_after_fg,
                    incoming_rate=rate_fg,
                    valuation_rate=rate_fg,
                    source_document_type="SUBCONTRACTING_RECEIPT_FG",
                    source_document_id=scr.scr_id,
                )
            )

        # 3. Post double-entry General Ledger Entries
        if total_fg_valuation > Decimal("0.0000"):
            gl_tx_id = uuid.uuid4()
            f_year = posting_date.year
            f_period = posting_date.month

            # Debit: Stock In Hand (Finished Goods)
            session.add(
                GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=gl_tx_id,
                    posting_date=posting_date,
                    fiscal_year=f_year,
                    fiscal_period=f_period,
                    account_code="1300-STOCK-IN-HAND",
                    cost_center="DEFAULT",
                    debit_amount=total_fg_valuation,
                    credit_amount=Decimal("0.0000"),
                    currency="USD",
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="SUBCONTRACTING_RECEIPT",
                    source_document_id=scr.scr_id,
                )
            )

            # Credit: Stock In Hand (Raw Material Consumed)
            if total_component_cost > Decimal("0.0000"):
                session.add(
                    GeneralLedgerEntry(
                        tenant_id=tenant_id,
                        transaction_id=gl_tx_id,
                        posting_date=posting_date,
                        fiscal_year=f_year,
                        fiscal_period=f_period,
                        account_code="1300-STOCK-IN-HAND",
                        cost_center="DEFAULT",
                        debit_amount=Decimal("0.0000"),
                        credit_amount=total_component_cost,
                        currency="USD",
                        exchange_rate=Decimal("1.000000"),
                        source_document_type="SUBCONTRACTING_RECEIPT",
                        source_document_id=scr.scr_id,
                    )
                )

            # Credit: Stock Received But Not Billed / Accrued Expenses for Service Fee
            if total_service_cost > Decimal("0.0000"):
                session.add(
                    GeneralLedgerEntry(
                        tenant_id=tenant_id,
                        transaction_id=gl_tx_id,
                        posting_date=posting_date,
                        fiscal_year=f_year,
                        fiscal_period=f_period,
                        account_code="2100-STOCK-RECEIVED-NOT-BILLED",
                        cost_center="DEFAULT",
                        debit_amount=Decimal("0.0000"),
                        credit_amount=total_service_cost,
                        currency="USD",
                        exchange_rate=Decimal("1.000000"),
                        source_document_type="SUBCONTRACTING_RECEIPT",
                        source_document_id=scr.scr_id,
                    )
                )

        # 4. Check if order completed
        if total_rec_fg >= total_ordered_fg:
            sco.status = "COMPLETED"

        await session.flush()
        return await self.get_subcontracting_receipt(session, tenant_id, scr.scr_id)  # type: ignore

    async def get_subcontracting_order(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sco_id: uuid.UUID,
    ) -> SubcontractingOrder | None:
        """Fetches Subcontracting Order with items and supplied components."""
        stmt = (
            select(SubcontractingOrder)
            .options(
                selectinload(SubcontractingOrder.items).selectinload(SubcontractingOrderItem.item),
                selectinload(SubcontractingOrder.supplied_items).selectinload(SubcontractingSuppliedItem.raw_item),
                selectinload(SubcontractingOrder.supplied_items).selectinload(SubcontractingSuppliedItem.source_warehouse),
                selectinload(SubcontractingOrder.supplied_items).selectinload(SubcontractingSuppliedItem.supplier_warehouse),
                selectinload(SubcontractingOrder.supplier),
            )
            .where(
                SubcontractingOrder.tenant_id == tenant_id,
                SubcontractingOrder.sco_id == sco_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_subcontracting_orders(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[SubcontractingOrder]:
        """Lists Subcontracting Orders."""
        stmt = (
            select(SubcontractingOrder)
            .options(
                selectinload(SubcontractingOrder.items).selectinload(SubcontractingOrderItem.item),
                selectinload(SubcontractingOrder.supplied_items).selectinload(SubcontractingSuppliedItem.raw_item),
                selectinload(SubcontractingOrder.supplier),
            )
            .where(SubcontractingOrder.tenant_id == tenant_id)
        )
        if supplier_id:
            stmt = stmt.where(SubcontractingOrder.supplier_id == supplier_id)
        if status:
            stmt = stmt.where(SubcontractingOrder.status == status.upper())
        stmt = stmt.order_by(SubcontractingOrder.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_subcontracting_receipt(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        scr_id: uuid.UUID,
    ) -> SubcontractingReceipt | None:
        """Fetches Subcontracting Receipt."""
        stmt = (
            select(SubcontractingReceipt)
            .options(
                selectinload(SubcontractingReceipt.items).selectinload(SubcontractingReceiptItem.item),
                selectinload(SubcontractingReceipt.order),
                selectinload(SubcontractingReceipt.supplier),
                selectinload(SubcontractingReceipt.target_warehouse),
            )
            .where(
                SubcontractingReceipt.tenant_id == tenant_id,
                SubcontractingReceipt.scr_id == scr_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_subcontracting_receipts(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sco_id: uuid.UUID | None = None,
    ) -> list[SubcontractingReceipt]:
        """Lists Subcontracting Receipts."""
        stmt = (
            select(SubcontractingReceipt)
            .options(
                selectinload(SubcontractingReceipt.items).selectinload(SubcontractingReceiptItem.item),
                selectinload(SubcontractingReceipt.supplier),
                selectinload(SubcontractingReceipt.target_warehouse),
            )
            .where(SubcontractingReceipt.tenant_id == tenant_id)
        )
        if sco_id:
            stmt = stmt.where(SubcontractingReceipt.sco_id == sco_id)
        stmt = stmt.order_by(SubcontractingReceipt.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


subcontracting_service = SubcontractingService()
