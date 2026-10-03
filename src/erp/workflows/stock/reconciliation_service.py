"""Stock Reconciliation Service: Physical count audits, variance calculation, and GL adjustments."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import (
    Item,
    StockLedgerEntry,
    StockLevel,
    StockReconciliation,
    StockReconciliationItem,
    Warehouse,
)
from erp.db.models.ledger import GeneralLedgerEntry


class ReconciliationService:
    """Core domain logic for Physical Stock Reconciliations."""

    async def create_reconciliation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        reconciliation_number: str,
        posting_date: date | None = None,
        posting_time: time | None = None,
        purpose: str = "STOCK_RECONCILIATION",
        expense_account: str = "5200-STOCK-ADJUSTMENT",
        items: list[dict[str, Any]] | None = None,
    ) -> StockReconciliation:
        """Creates draft stock reconciliation voucher calculating variance quantities and amounts."""
        if not posting_date:
            posting_date = date.today()
        if not posting_time:
            posting_time = datetime.now().time()

        recon = StockReconciliation(
            tenant_id=tenant_id,
            reconciliation_number=reconciliation_number,
            posting_date=posting_date,
            posting_time=posting_time,
            purpose=purpose,
            expense_account=expense_account,
            status="DRAFT",
            total_variance_value=Decimal("0.0000"),
        )
        session.add(recon)
        await session.flush()

        total_variance_value = Decimal("0.0000")

        if items:
            for it in items:
                item_id = (
                    uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
                )
                warehouse_id = (
                    uuid.UUID(str(it["warehouse_id"]))
                    if isinstance(it["warehouse_id"], str)
                    else it["warehouse_id"]
                )

                # Fetch current system stock level
                stmt = select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == item_id,
                    StockLevel.warehouse_id == warehouse_id,
                )
                level = (await session.execute(stmt)).scalar_one_or_none()

                current_qty = level.current_qty if level else Decimal("0.0000")
                current_rate = level.valuation_rate if level else Decimal("0.0000")

                reconciled_qty = Decimal(str(it["reconciled_qty"]))
                reconciled_rate = Decimal(str(it.get("reconciled_valuation_rate", current_rate)))

                difference_qty = reconciled_qty - current_qty
                # Valuation delta: (Physical Qty * Physical Rate) - (Book Qty * Book Rate)
                diff_amount = (reconciled_qty * reconciled_rate) - (current_qty * current_rate)
                total_variance_value += diff_amount

                recon_item = StockReconciliationItem(
                    tenant_id=tenant_id,
                    reconciliation_id=recon.reconciliation_id,
                    item_id=item_id,
                    warehouse_id=warehouse_id,
                    current_qty=current_qty,
                    reconciled_qty=reconciled_qty,
                    difference_qty=difference_qty,
                    current_valuation_rate=current_rate,
                    reconciled_valuation_rate=reconciled_rate,
                    difference_amount=diff_amount,
                )
                session.add(recon_item)

        recon.total_variance_value = total_variance_value
        await session.flush()

        return await self.get_reconciliation(session, tenant_id, recon.reconciliation_id)  # type: ignore

    async def submit_reconciliation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        reconciliation_id: uuid.UUID,
    ) -> StockReconciliation:
        """Applies physical inventory reconciliation, posting StockLedgerEntries and GL adjustments."""
        recon = await self.get_reconciliation(session, tenant_id, reconciliation_id)
        if not recon:
            raise ValueError(f"Stock Reconciliation {reconciliation_id} not found.")
        if recon.status != "DRAFT":
            raise ValueError(f"Reconciliation already in status '{recon.status}'.")

        posting_dt = datetime.combine(recon.posting_date, recon.posting_time)

        for line in recon.items:
            # 1. Update StockLevel cache
            stmt = select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == line.item_id,
                StockLevel.warehouse_id == line.warehouse_id,
            )
            level = (await session.execute(stmt)).scalar_one_or_none()
            if not level:
                level = StockLevel(
                    tenant_id=tenant_id,
                    item_id=line.item_id,
                    warehouse_id=line.warehouse_id,
                    current_qty=line.reconciled_qty,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=line.reconciled_qty,
                    valuation_rate=line.reconciled_valuation_rate,
                )
                session.add(level)
            else:
                level.current_qty = line.reconciled_qty
                level.available_qty = line.reconciled_qty - level.reserved_qty
                level.valuation_rate = line.reconciled_valuation_rate

            # 2. Write adjusting StockLedgerEntry
            sle = StockLedgerEntry(
                tenant_id=tenant_id,
                posting_datetime=posting_dt,
                item_id=line.item_id,
                warehouse_id=line.warehouse_id,
                actual_qty=line.difference_qty,
                qty_after_transaction=line.reconciled_qty,
                incoming_rate=line.reconciled_valuation_rate if line.difference_qty > 0 else Decimal("0.0000"),
                outgoing_rate=line.current_valuation_rate if line.difference_qty < 0 else Decimal("0.0000"),
                valuation_rate=line.reconciled_valuation_rate,
                stock_value_difference=line.difference_amount,
                source_document_type="STOCK_RECONCILIATION",
                source_document_id=recon.reconciliation_id,
            )
            session.add(sle)

        # 3. Post General Ledger Variance Entries
        f_year = recon.posting_date.year
        f_period = recon.posting_date.month
        tx_id = uuid.uuid4()

        if recon.total_variance_value > Decimal("0.0000"):
            # Inventory Gain: Debit Stock Asset, Credit Adjustment
            session.add(
                GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=tx_id,
                    posting_date=recon.posting_date,
                    fiscal_year=f_year,
                    fiscal_period=f_period,
                    account_code="1300-STOCK-IN-HAND",
                    cost_center="DEFAULT",
                    debit_amount=recon.total_variance_value,
                    credit_amount=Decimal("0.0000"),
                    currency="USD",
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="STOCK_RECONCILIATION",
                    source_document_id=recon.reconciliation_id,
                )
            )
            session.add(
                GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=tx_id,
                    posting_date=recon.posting_date,
                    fiscal_year=f_year,
                    fiscal_period=f_period,
                    account_code=recon.expense_account,
                    cost_center="DEFAULT",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=recon.total_variance_value,
                    currency="USD",
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="STOCK_RECONCILIATION",
                    source_document_id=recon.reconciliation_id,
                )
            )
        elif recon.total_variance_value < Decimal("0.0000"):
            # Inventory Loss: Debit Adjustment Expense, Credit Stock Asset
            abs_loss = abs(recon.total_variance_value)
            session.add(
                GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=tx_id,
                    posting_date=recon.posting_date,
                    fiscal_year=f_year,
                    fiscal_period=f_period,
                    account_code=recon.expense_account,
                    cost_center="DEFAULT",
                    debit_amount=abs_loss,
                    credit_amount=Decimal("0.0000"),
                    currency="USD",
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="STOCK_RECONCILIATION",
                    source_document_id=recon.reconciliation_id,
                )
            )
            session.add(
                GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=tx_id,
                    posting_date=recon.posting_date,
                    fiscal_year=f_year,
                    fiscal_period=f_period,
                    account_code="1300-STOCK-IN-HAND",
                    cost_center="DEFAULT",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=abs_loss,
                    currency="USD",
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="STOCK_RECONCILIATION",
                    source_document_id=recon.reconciliation_id,
                )
            )

        recon.status = "SUBMITTED"
        await session.flush()
        return recon

    async def get_reconciliation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        reconciliation_id: uuid.UUID,
    ) -> StockReconciliation | None:
        """Fetches reconciliation voucher with item lines."""
        stmt = (
            select(StockReconciliation)
            .options(
                selectinload(StockReconciliation.items).selectinload(StockReconciliationItem.item),
                selectinload(StockReconciliation.items).selectinload(StockReconciliationItem.warehouse),
            )
            .where(
                StockReconciliation.tenant_id == tenant_id,
                StockReconciliation.reconciliation_id == reconciliation_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_reconciliations(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[StockReconciliation]:
        """Lists stock reconciliations for tenant."""
        stmt = (
            select(StockReconciliation)
            .options(
                selectinload(StockReconciliation.items).selectinload(StockReconciliationItem.item),
            )
            .where(StockReconciliation.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(StockReconciliation.status == status.upper())
        stmt = stmt.order_by(StockReconciliation.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


reconciliation_service = ReconciliationService()
