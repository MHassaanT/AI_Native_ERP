"""Domain Service for Fixed Assets Lifecycle, Depreciation Engine & GL Postings."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
from dateutil.relativedelta import relativedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.assets import (
    Asset,
    AssetCategory,
    AssetDepreciationSchedule,
    AssetLocation,
    AssetMovement,
    AssetRepair,
)
from erp.db.models.ledger import GeneralLedgerEntry


class AssetService:
    """Enterprise Fixed Assets management with multi-method depreciation and GL integration."""

    async def create_category(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        category_name: str,
        depreciation_method: str = "STRAIGHT_LINE",
        total_number_of_depreciations: int = 36,
        frequency_in_months: int = 1,
        fixed_asset_account: str = "1500-FIXED-ASSETS",
        accumulated_depreciation_account: str = "1550-ACCUMULATED-DEPRECIATION",
        depreciation_expense_account: str = "5200-DEP-MACHINERY",
    ) -> AssetCategory:
        cat_id = uuid.uuid4()
        category = AssetCategory(
            category_id=cat_id,
            tenant_id=tenant_id,
            category_name=category_name,
            depreciation_method=depreciation_method.upper(),
            total_number_of_depreciations=total_number_of_depreciations,
            frequency_in_months=frequency_in_months,
            fixed_asset_account=fixed_asset_account,
            accumulated_depreciation_account=accumulated_depreciation_account,
            depreciation_expense_account=depreciation_expense_account,
        )
        session.add(category)
        await session.flush()
        return category

    async def list_categories(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> List[AssetCategory]:
        stmt = select(AssetCategory).where(AssetCategory.tenant_id == tenant_id).order_by(AssetCategory.category_name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_category(
        self, session: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
    ) -> Optional[AssetCategory]:
        stmt = select(AssetCategory).where(
            AssetCategory.tenant_id == tenant_id, AssetCategory.category_id == category_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_location(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        location_name: str,
        parent_location_id: Optional[uuid.UUID] = None,
    ) -> AssetLocation:
        loc_id = uuid.uuid4()
        location = AssetLocation(
            location_id=loc_id,
            tenant_id=tenant_id,
            location_name=location_name,
            parent_location_id=parent_location_id,
        )
        session.add(location)
        await session.flush()
        return location

    async def list_locations(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> List[AssetLocation]:
        stmt = select(AssetLocation).where(AssetLocation.tenant_id == tenant_id).order_by(AssetLocation.location_name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create_asset(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_code: str,
        asset_name: str,
        asset_category_id: uuid.UUID,
        purchase_date: date,
        available_for_use_date: date,
        gross_purchase_amount: Decimal,
        salvage_value: Decimal = Decimal("0.0000"),
        location_id: Optional[uuid.UUID] = None,
        custodian_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
        auto_generate_schedule: bool = True,
    ) -> Asset:
        category = await self.get_category(session, tenant_id, asset_category_id)
        if not category:
            raise ValueError(f"Asset Category {asset_category_id} not found.")

        asset_id = uuid.uuid4()
        asset = Asset(
            asset_id=asset_id,
            tenant_id=tenant_id,
            asset_code=asset_code,
            asset_name=asset_name,
            asset_category_id=asset_category_id,
            location_id=location_id,
            custodian_id=custodian_id,
            purchase_date=purchase_date,
            available_for_use_date=available_for_use_date,
            gross_purchase_amount=gross_purchase_amount,
            salvage_value=salvage_value,
            current_book_value=gross_purchase_amount,
            accumulated_depreciation=Decimal("0.0000"),
            status="SUBMITTED",
            notes=notes,
        )
        session.add(asset)
        await session.flush()

        if auto_generate_schedule:
            await self.generate_depreciation_schedule(session, tenant_id, asset, category)

        return asset

    async def generate_depreciation_schedule(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset: Asset,
        category: AssetCategory,
    ) -> List[AssetDepreciationSchedule]:
        del_stmt = select(AssetDepreciationSchedule).where(
            AssetDepreciationSchedule.tenant_id == tenant_id,
            AssetDepreciationSchedule.asset_id == asset.asset_id,
            AssetDepreciationSchedule.is_posted == False,
        )
        existing = await session.execute(del_stmt)
        for s in existing.scalars().all():
            await session.delete(s)
        await session.flush()

        total_periods = category.total_number_of_depreciations
        freq_months = category.frequency_in_months
        method = category.depreciation_method.upper()

        depreciable_base = asset.gross_purchase_amount - asset.salvage_value
        if depreciable_base <= Decimal("0.0000") or total_periods <= 0:
            return []

        schedules: List[AssetDepreciationSchedule] = []
        running_book_value = asset.gross_purchase_amount
        running_accumulated = Decimal("0.0000")

        if method == "STRAIGHT_LINE":
            period_amount = (depreciable_base / Decimal(str(total_periods))).quantize(Decimal("0.0001"))
            for i in range(1, total_periods + 1):
                sched_date = asset.available_for_use_date + relativedelta(months=i * freq_months)
                if i == total_periods:
                    dep_amount = depreciable_base - running_accumulated
                else:
                    dep_amount = period_amount

                running_accumulated += dep_amount
                running_book_value -= dep_amount

                row = AssetDepreciationSchedule(
                    schedule_id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    asset_id=asset.asset_id,
                    schedule_date=sched_date,
                    depreciation_amount=dep_amount,
                    accumulated_depreciation=running_accumulated,
                    book_value_after_depreciation=running_book_value,
                    is_posted=False,
                )
                session.add(row)
                schedules.append(row)

        elif method in ["DOUBLE_DECLINING", "WRITTEN_DOWN_VALUE"]:
            periodic_rate = Decimal("2.0") / Decimal(str(total_periods))
            for i in range(1, total_periods + 1):
                sched_date = asset.available_for_use_date + relativedelta(months=i * freq_months)
                if running_book_value <= asset.salvage_value:
                    dep_amount = Decimal("0.0000")
                else:
                    proposed = (running_book_value * periodic_rate).quantize(Decimal("0.0001"))
                    if running_book_value - proposed < asset.salvage_value:
                        dep_amount = max(Decimal("0.0000"), running_book_value - asset.salvage_value)
                    else:
                        dep_amount = proposed

                if i == total_periods and running_book_value > asset.salvage_value:
                    dep_amount = max(Decimal("0.0000"), running_book_value - asset.salvage_value)

                running_accumulated += dep_amount
                running_book_value -= dep_amount

                row = AssetDepreciationSchedule(
                    schedule_id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    asset_id=asset.asset_id,
                    schedule_date=sched_date,
                    depreciation_amount=dep_amount,
                    accumulated_depreciation=running_accumulated,
                    book_value_after_depreciation=running_book_value,
                    is_posted=False,
                )
                session.add(row)
                schedules.append(row)

        await session.flush()
        return schedules

    async def post_depreciation_entry(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        schedule_id: uuid.UUID,
    ) -> GeneralLedgerEntry:
        stmt = (
            select(AssetDepreciationSchedule)
            .options(selectinload(AssetDepreciationSchedule.asset).selectinload(Asset.category))
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.schedule_id == schedule_id,
            )
        )
        res = await session.execute(stmt)
        sched = res.scalar_one_or_none()
        if not sched:
            raise ValueError(f"Depreciation Schedule {schedule_id} not found.")
        if sched.is_posted:
            raise ValueError("This depreciation schedule period has already been posted to the General Ledger.")

        asset = sched.asset
        category = asset.category
        dep_amount = sched.depreciation_amount

        tx_id = uuid.uuid4()
        post_date = sched.schedule_date

        dr_entry = GeneralLedgerEntry(
            entry_id=uuid.uuid4(),
            tenant_id=tenant_id,
            transaction_id=tx_id,
            posting_date=post_date,
            fiscal_year=post_date.year,
            fiscal_period=post_date.month,
            account_code=category.depreciation_expense_account,
            cost_center="OPERATIONS",
            debit_amount=dep_amount,
            credit_amount=Decimal("0.0000"),
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="ASSET_DEPRECIATION",
            source_document_id=sched.schedule_id,
        )

        cr_entry = GeneralLedgerEntry(
            entry_id=uuid.uuid4(),
            tenant_id=tenant_id,
            transaction_id=tx_id,
            posting_date=post_date,
            fiscal_year=post_date.year,
            fiscal_period=post_date.month,
            account_code=category.accumulated_depreciation_account,
            cost_center="OPERATIONS",
            debit_amount=Decimal("0.0000"),
            credit_amount=dep_amount,
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="ASSET_DEPRECIATION",
            source_document_id=sched.schedule_id,
        )

        session.add(dr_entry)
        session.add(cr_entry)

        sched.is_posted = True
        sched.posted_at = datetime.now(timezone.utc)
        sched.journal_entry_id = tx_id

        asset.accumulated_depreciation += dep_amount
        asset.current_book_value -= dep_amount
        asset.status = "IN_USE"
        if asset.current_book_value <= asset.salvage_value:
            asset.status = "FULLY_DEPRECIATED"

        await session.flush()
        return dr_entry

    async def record_asset_movement(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        to_location_id: Optional[uuid.UUID] = None,
        to_custodian_id: Optional[uuid.UUID] = None,
        movement_date: Optional[date] = None,
        purpose: Optional[str] = None,
    ) -> AssetMovement:
        asset = await self.get_asset(session, tenant_id, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found.")

        movement_id = uuid.uuid4()
        movement = AssetMovement(
            movement_id=movement_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            from_location_id=asset.location_id,
            to_location_id=to_location_id,
            from_custodian_id=asset.custodian_id,
            to_custodian_id=to_custodian_id,
            movement_date=movement_date or date.today(),
            purpose=purpose,
        )
        session.add(movement)

        if to_location_id:
            asset.location_id = to_location_id
        if to_custodian_id:
            asset.custodian_id = to_custodian_id

        await session.flush()
        return movement

    async def record_asset_repair(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        repair_cost: Decimal,
        repair_description: str,
        repair_date: Optional[date] = None,
        is_capitalized: bool = False,
    ) -> AssetRepair:
        asset = await self.get_asset(session, tenant_id, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found.")

        repair_id = uuid.uuid4()
        repair = AssetRepair(
            repair_id=repair_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            repair_date=repair_date or date.today(),
            repair_cost=repair_cost,
            repair_description=repair_description,
            is_capitalized=is_capitalized,
        )
        session.add(repair)

        if is_capitalized and repair_cost > Decimal("0.0000"):
            category = await self.get_category(session, tenant_id, asset.asset_category_id)
            tx_id = uuid.uuid4()
            r_date = repair.repair_date

            dr = GeneralLedgerEntry(
                entry_id=uuid.uuid4(),
                tenant_id=tenant_id,
                transaction_id=tx_id,
                posting_date=r_date,
                fiscal_year=r_date.year,
                fiscal_period=r_date.month,
                account_code=category.fixed_asset_account if category else "1500-FIXED-ASSETS",
                cost_center="OPERATIONS",
                debit_amount=repair_cost,
                credit_amount=Decimal("0.0000"),
                currency="USD",
                exchange_rate=Decimal("1.000000"),
                source_document_type="ASSET_REPAIR_CAPITALIZATION",
                source_document_id=repair_id,
            )
            cr = GeneralLedgerEntry(
                entry_id=uuid.uuid4(),
                tenant_id=tenant_id,
                transaction_id=tx_id,
                posting_date=r_date,
                fiscal_year=r_date.year,
                fiscal_period=r_date.month,
                account_code="1110-OPERATING-CASH",
                cost_center="OPERATIONS",
                debit_amount=Decimal("0.0000"),
                credit_amount=repair_cost,
                currency="USD",
                exchange_rate=Decimal("1.000000"),
                source_document_type="ASSET_REPAIR_CAPITALIZATION",
                source_document_id=repair_id,
            )
            session.add(dr)
            session.add(cr)
            repair.journal_entry_id = tx_id

            asset.gross_purchase_amount += repair_cost
            asset.current_book_value += repair_cost

        await session.flush()
        return repair

    async def scrap_asset(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        disposal_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> Asset:
        asset = await self.get_asset(session, tenant_id, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found.")

        category = await self.get_category(session, tenant_id, asset.asset_category_id)
        d_date = disposal_date or date.today()
        tx_id = uuid.uuid4()

        remaining_value = asset.current_book_value
        gross_value = asset.gross_purchase_amount
        accum_dep = asset.accumulated_depreciation

        if remaining_value > Decimal("0.0000"):
            dr_loss = GeneralLedgerEntry(
                entry_id=uuid.uuid4(),
                tenant_id=tenant_id,
                transaction_id=tx_id,
                posting_date=d_date,
                fiscal_year=d_date.year,
                fiscal_period=d_date.month,
                account_code="5300-LOSS-ON-ASSET-DISPOSAL",
                cost_center="OPERATIONS",
                debit_amount=remaining_value,
                credit_amount=Decimal("0.0000"),
                currency="USD",
                exchange_rate=Decimal("1.000000"),
                source_document_type="ASSET_DISPOSAL",
                source_document_id=asset.asset_id,
            )
            session.add(dr_loss)

        if accum_dep > Decimal("0.0000"):
            dr_accum = GeneralLedgerEntry(
                entry_id=uuid.uuid4(),
                tenant_id=tenant_id,
                transaction_id=tx_id,
                posting_date=d_date,
                fiscal_year=d_date.year,
                fiscal_period=d_date.month,
                account_code=category.accumulated_depreciation_account if category else "1550-ACCUMULATED-DEPRECIATION",
                cost_center="OPERATIONS",
                debit_amount=accum_dep,
                credit_amount=Decimal("0.0000"),
                currency="USD",
                exchange_rate=Decimal("1.000000"),
                source_document_type="ASSET_DISPOSAL",
                source_document_id=asset.asset_id,
            )
            session.add(dr_accum)

        cr_asset = GeneralLedgerEntry(
            entry_id=uuid.uuid4(),
            tenant_id=tenant_id,
            transaction_id=tx_id,
            posting_date=d_date,
            fiscal_year=d_date.year,
            fiscal_period=d_date.month,
            account_code=category.fixed_asset_account if category else "1500-FIXED-ASSETS",
            cost_center="OPERATIONS",
            debit_amount=Decimal("0.0000"),
            credit_amount=gross_value,
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="ASSET_DISPOSAL",
            source_document_id=asset.asset_id,
        )
        session.add(cr_asset)

        asset.status = "SCRAPPED"
        asset.current_book_value = Decimal("0.0000")
        if notes:
            asset.notes = f"{asset.notes or ''} [Scrapped: {notes}]"

        await session.flush()
        return asset

    async def get_asset(
        self, session: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID
    ) -> Optional[Asset]:
        stmt = (
            select(Asset)
            .options(
                selectinload(Asset.category),
                selectinload(Asset.schedules),
                selectinload(Asset.movements),
                selectinload(Asset.repairs),
            )
            .where(Asset.tenant_id == tenant_id, Asset.asset_id == asset_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_assets(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
    ) -> List[Asset]:
        stmt = (
            select(Asset)
            .options(selectinload(Asset.category))
            .where(Asset.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(Asset.status == status.upper())
        if category_id:
            stmt = stmt.where(Asset.asset_category_id == category_id)
        stmt = stmt.order_by(Asset.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


asset_service = AssetService()
