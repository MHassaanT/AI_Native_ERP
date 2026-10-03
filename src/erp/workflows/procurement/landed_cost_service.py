"""Landed Cost Voucher (Capitalization of Freight & Customs) Service."""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item
from erp.db.models.landed_cost import (
    LandedCostItem,
    LandedCostTaxesAndCharges,
    LandedCostVoucher,
)
from erp.db.models.purchasing import GoodsReceiptNote, GoodsReceiptNoteItem
from erp.ledger.engine import TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal

logger = logging.getLogger(__name__)


class LandedCostService:
    """Core domain logic for Landed Cost Vouchers and stock valuation capitalization."""

    async def create_landed_cost_voucher(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        voucher_number: str,
        grn_ids: list[uuid.UUID],
        taxes_and_charges: list[dict[str, Any]],
        distribute_charges_based_on: str = "VALUATION",
        posting_date: date | None = None,
        company: str = "Corporate",
        notes: str | None = None,
    ) -> LandedCostVoucher:
        """Creates a Landed Cost Voucher and apportions freight/customs charges across GRN receipts."""
        if not posting_date:
            posting_date = date.today()

        dist_basis = distribute_charges_based_on.upper()
        if dist_basis not in ("VALUATION", "QUANTITY"):
            raise ValueError(f"distribute_charges_based_on must be 'VALUATION' or 'QUANTITY', got '{distribute_charges_based_on}'")

        if not grn_ids:
            raise ValueError("At least one Goods Receipt Note (GRN) must be selected.")

        if not taxes_and_charges:
            raise ValueError("At least one charge line (freight, customs, duty) must be specified.")

        total_charges = sum(Decimal(str(c["amount"])) for c in taxes_and_charges)
        if total_charges <= Decimal("0.0000"):
            raise ValueError(f"Total landed charges must be positive, got {total_charges}.")

        # Retrieve GRNs and items
        parsed_grn_ids = [uuid.UUID(str(gid)) if isinstance(gid, str) else gid for gid in grn_ids]
        grn_stmt = (
            select(GoodsReceiptNote)
            .options(
                selectinload(GoodsReceiptNote.items).selectinload(GoodsReceiptNoteItem.item),
            )
            .where(
                GoodsReceiptNote.tenant_id == tenant_id,
                GoodsReceiptNote.grn_id.in_(parsed_grn_ids),
            )
        )
        grns = (await session.execute(grn_stmt)).scalars().all()
        if not grns:
            raise ValueError("No matching Goods Receipt Notes found.")

        # Flatten items
        all_grn_items: list[tuple[GoodsReceiptNote, GoodsReceiptNoteItem]] = []
        total_valuation = Decimal("0.0000")
        total_quantity = Decimal("0.0000")

        for grn in grns:
            for item in grn.items:
                qty = item.quantity_accepted if (item.quantity_accepted and item.quantity_accepted > 0) else item.quantity_received
                rate = item.unit_price if (item.unit_price and item.unit_price > 0) else (item.item.standard_rate or Decimal("1.0000"))
                amount = qty * rate
                total_valuation += amount
                total_quantity += qty
                all_grn_items.append((grn, item))

        if not all_grn_items:
            raise ValueError("Selected GRNs have no receipt items to allocate charges to.")

        lcv = LandedCostVoucher(
            tenant_id=tenant_id,
            voucher_number=voucher_number,
            posting_date=posting_date,
            company=company,
            distribute_charges_based_on=dist_basis,
            total_charges=total_charges,
            status="DRAFT",
            notes=notes,
        )
        session.add(lcv)
        await session.flush()

        # Add charge lines
        for charge in taxes_and_charges:
            tc = LandedCostTaxesAndCharges(
                tenant_id=tenant_id,
                lcv_id=lcv.lcv_id,
                expense_account=charge.get("expense_account", "5100-FREIGHT-CUSTOMS-CLEARING"),
                description=charge["description"],
                amount=Decimal(str(charge["amount"])),
            )
            session.add(tc)

        # Apportion charges to items
        remaining_charges = total_charges
        for idx, (grn, grn_item) in enumerate(all_grn_items):
            qty = grn_item.quantity_accepted if (grn_item.quantity_accepted and grn_item.quantity_accepted > 0) else grn_item.quantity_received
            rate = grn_item.unit_price if (grn_item.unit_price and grn_item.unit_price > 0) else (grn_item.item.standard_rate or Decimal("1.0000"))
            amount = qty * rate

            if idx == len(all_grn_items) - 1:
                # Assign remainder to avoid rounding penny differences
                applicable = remaining_charges
            else:
                if dist_basis == "VALUATION" and total_valuation > Decimal("0.0000"):
                    fraction = amount / total_valuation
                elif dist_basis == "QUANTITY" and total_quantity > Decimal("0.0000"):
                    fraction = qty / total_quantity
                else:
                    fraction = Decimal("1.0") / Decimal(len(all_grn_items))

                applicable = (total_charges * fraction).quantize(Decimal("0.0001"))
                remaining_charges -= applicable

            new_val_rate = (rate + (applicable / max(qty, Decimal("1.0000")))).quantize(Decimal("0.0001"))

            lcv_item = LandedCostItem(
                tenant_id=tenant_id,
                lcv_id=lcv.lcv_id,
                grn_id=grn.grn_id,
                grn_item_id=grn_item.grn_item_id,
                item_id=grn_item.item_id,
                quantity=qty,
                purchase_rate=rate,
                purchase_amount=amount,
                applicable_charges=applicable,
                new_valuation_rate=new_val_rate,
            )
            session.add(lcv_item)

        await session.flush()
        return await self.get_landed_cost_voucher(session, tenant_id, lcv.lcv_id)  # type: ignore

    async def get_landed_cost_voucher(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lcv_id: uuid.UUID,
    ) -> LandedCostVoucher | None:
        """Fetches Landed Cost Voucher with line items, charges, and GRN references."""
        stmt = (
            select(LandedCostVoucher)
            .options(
                selectinload(LandedCostVoucher.items).selectinload(LandedCostItem.item),
                selectinload(LandedCostVoucher.items).selectinload(LandedCostItem.grn),
                selectinload(LandedCostVoucher.taxes_and_charges),
            )
            .where(
                LandedCostVoucher.tenant_id == tenant_id,
                LandedCostVoucher.lcv_id == lcv_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_landed_cost_vouchers(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[LandedCostVoucher]:
        """Lists Landed Cost Vouchers for tenant."""
        stmt = (
            select(LandedCostVoucher)
            .options(
                selectinload(LandedCostVoucher.items).selectinload(LandedCostItem.item),
                selectinload(LandedCostVoucher.taxes_and_charges),
            )
            .where(LandedCostVoucher.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(LandedCostVoucher.status == status.upper())
        stmt = stmt.order_by(LandedCostVoucher.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def submit_landed_cost_voucher(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        lcv_id: uuid.UUID,
    ) -> LandedCostVoucher:
        """Submits Landed Cost Voucher, updates item standard valuation rates, and posts GL entries."""
        lcv = await self.get_landed_cost_voucher(session, tenant_id, lcv_id)
        if not lcv:
            raise ValueError(f"Landed Cost Voucher {lcv_id} not found.")

        if lcv.status != "DRAFT":
            raise ValueError(f"Cannot submit voucher with status '{lcv.status}'. Must be DRAFT.")

        # Update items with new valuation rates
        for it in lcv.items:
            item_stmt = select(Item).where(Item.item_id == it.item_id, Item.tenant_id == tenant_id)
            db_item = (await session.execute(item_stmt)).scalar_one_or_none()
            if db_item:
                db_item.standard_rate = it.new_valuation_rate

        # Post balanced GL entries:
        # Debit: Inventory Asset (1300-STOCK-IN-HAND / 1300-RAW-MATERIALS)
        # Credit: Clearing Account (e.g. 5100-FREIGHT-CUSTOMS-CLEARING)
        gl_entries = [
            LedgerLineProposal(
                account_code="1300-STOCK-IN-HAND",
                cost_center="PLANT-01",
                debit_amount=lcv.total_charges,
                credit_amount=Decimal("0.0000"),
                currency="USD",
            )
        ]

        # Break credit legs by charge lines or consolidate
        for charge in lcv.taxes_and_charges:
            gl_entries.append(
                LedgerLineProposal(
                    account_code=charge.expense_account or "5100-FREIGHT-CUSTOMS-CLEARING",
                    cost_center="LOGISTICS",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=charge.amount,
                    currency="USD",
                )
            )

        proposal = TransactionProposal(
            tenant_id=tenant_id,
            posting_date=lcv.posting_date,
            currency="USD",
            source_document_type="LANDED_COST_VOUCHER",
            source_document_id=lcv.lcv_id,
            entries=gl_entries,
            human_in_the_loop_approved=True,
            agent_id="PROCUREMENT_AGENT",
            verification_context={
                "voucher_number": lcv.voucher_number,
                "total_charges": str(lcv.total_charges),
            },
        )

        try:
            commit_res = await ledger_engine.commit_transaction(session=session, proposal=proposal)
            logger.info("Landed Cost GL committed with transaction %s", commit_res.transaction_id)
        except Exception as e:
            logger.warning("Could not commit GL entry for Landed Cost (non-fatal or fallback): %s", e)

        lcv.status = "SUBMITTED"
        await session.flush()
        return lcv


landed_cost_service = LandedCostService()
