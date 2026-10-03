"""Foreign Exchange Rates and Automated Balance Sheet Revaluation Engine."""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.currency import CurrencyExchangeRate, ExchangeRateRevaluation
from erp.db.models.ledger import GeneralLedgerEntry

logger = logging.getLogger(__name__)


class ExchangeService:
    """Core domain service for FX currency pair conversion and unrealized gain/loss revaluations."""

    async def set_exchange_rate(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_currency: str,
        to_currency: str,
        exchange_rate: Decimal,
        effective_date: Optional[date] = None,
    ) -> CurrencyExchangeRate:
        """Sets or updates spot/conversion rate for a currency pair."""
        if not effective_date:
            effective_date = date.today()

        stmt = select(CurrencyExchangeRate).where(
            CurrencyExchangeRate.tenant_id == tenant_id,
            CurrencyExchangeRate.from_currency == from_currency.upper(),
            CurrencyExchangeRate.to_currency == to_currency.upper(),
            CurrencyExchangeRate.effective_date == effective_date,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.exchange_rate = exchange_rate
            await session.flush()
            return existing

        rate_obj = CurrencyExchangeRate(
            tenant_id=tenant_id,
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
            exchange_rate=exchange_rate,
            effective_date=effective_date,
        )
        session.add(rate_obj)
        await session.flush()
        return rate_obj

    async def get_latest_rate(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_currency: str,
        to_currency: str,
        as_of_date: Optional[date] = None,
    ) -> Decimal:
        """Retrieves most recent exchange rate for pair."""
        if from_currency.upper() == to_currency.upper():
            return Decimal("1.000000")

        if not as_of_date:
            as_of_date = date.today()

        stmt = (
            select(CurrencyExchangeRate.exchange_rate)
            .where(
                CurrencyExchangeRate.tenant_id == tenant_id,
                CurrencyExchangeRate.from_currency == from_currency.upper(),
                CurrencyExchangeRate.to_currency == to_currency.upper(),
                CurrencyExchangeRate.effective_date <= as_of_date,
            )
            .order_by(CurrencyExchangeRate.effective_date.desc())
            .limit(1)
        )
        val = (await session.execute(stmt)).scalar()
        if val is not None:
            return val

        # Check reciprocal
        recip_stmt = (
            select(CurrencyExchangeRate.exchange_rate)
            .where(
                CurrencyExchangeRate.tenant_id == tenant_id,
                CurrencyExchangeRate.from_currency == to_currency.upper(),
                CurrencyExchangeRate.to_currency == from_currency.upper(),
                CurrencyExchangeRate.effective_date <= as_of_date,
            )
            .order_by(CurrencyExchangeRate.effective_date.desc())
            .limit(1)
        )
        recip_val = (await session.execute(recip_stmt)).scalar()
        if recip_val and recip_val > 0:
            return (Decimal("1.000000") / recip_val).quantize(Decimal("0.000001"))

        return Decimal("1.000000")

    async def list_exchange_rates(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> List[CurrencyExchangeRate]:
        """Lists exchange rates configured for tenant."""
        stmt = (
            select(CurrencyExchangeRate)
            .where(CurrencyExchangeRate.tenant_id == tenant_id)
            .order_by(CurrencyExchangeRate.effective_date.desc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def execute_exchange_revaluation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        posting_date: date,
        base_currency: str = "USD",
        notes: Optional[str] = None,
    ) -> ExchangeRateRevaluation:
        """
        Period FX Revaluation:
        1. Identifies foreign currency GL balances for monetary accounts (Assets & Liabilities).
        2. Calculates new base currency value against spot rates.
        3. Computes unrealized foreign exchange gain/loss.
        4. Posts balanced GL journal entries to 4900-UNREALIZED-FX-GAIN-LOSS.
        """
        # Fetch open foreign currency GL entries for monetary accounts (1: Assets, 2: Liabilities)
        stmt = (
            select(
                GeneralLedgerEntry.account_code,
                GeneralLedgerEntry.currency,
                func.sum(GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount).label("net_balance"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date <= posting_date,
                GeneralLedgerEntry.currency != base_currency.upper(),
                or_(
                    GeneralLedgerEntry.account_code.startswith("1"),
                    GeneralLedgerEntry.account_code.startswith("2"),
                ),
            )
            .group_by(GeneralLedgerEntry.account_code, GeneralLedgerEntry.currency)
        )
        foreign_entries = (await session.execute(stmt)).all()

        total_gain_loss = Decimal("0.0000")
        rev_id = uuid.uuid4()
        rev_number = f"FX-REV-{posting_date.strftime('%Y%m')}-{rev_id.hex[:6].upper()}"

        tx_id = uuid.uuid4()
        gl_entries: List[GeneralLedgerEntry] = []

        for row in foreign_entries:
            curr = row.currency
            net_bal = row.net_balance
            if net_bal == 0:
                continue

            current_rate = await self.get_latest_rate(
                session, tenant_id, curr, base_currency, posting_date
            )
            # Revalued balance
            revalued_amt = (net_bal * current_rate).quantize(Decimal("0.0001"))
            diff = revalued_amt - net_bal

            if diff != 0:
                total_gain_loss += diff
                abs_diff = abs(diff)

                if diff > 0:
                    # Unrealized Gain: Debit Target Account, Credit 4900-UNREALIZED-EXCHANGE-GAIN-LOSS
                    gl_entries.append(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=posting_date,
                            fiscal_year=posting_date.year,
                            fiscal_period=posting_date.month,
                            account_code=row.account_code,
                            cost_center="DEFAULT",
                            debit_amount=abs_diff,
                            credit_amount=Decimal("0.0000"),
                            currency=base_currency,
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="EXCHANGE_REVALUATION",
                            source_document_id=rev_id,
                        )
                    )
                    gl_entries.append(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=posting_date,
                            fiscal_year=posting_date.year,
                            fiscal_period=posting_date.month,
                            account_code="4900-UNREALIZED-FX-GAIN-LOSS",
                            cost_center="DEFAULT",
                            debit_amount=Decimal("0.0000"),
                            credit_amount=abs_diff,
                            currency=base_currency,
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="EXCHANGE_REVALUATION",
                            source_document_id=rev_id,
                        )
                    )
                else:
                    # Unrealized Loss: Debit 4900-UNREALIZED-EXCHANGE-GAIN-LOSS, Credit Target Account
                    gl_entries.append(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=posting_date,
                            fiscal_year=posting_date.year,
                            fiscal_period=posting_date.month,
                            account_code="4900-UNREALIZED-FX-GAIN-LOSS",
                            cost_center="DEFAULT",
                            debit_amount=abs_diff,
                            credit_amount=Decimal("0.0000"),
                            currency=base_currency,
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="EXCHANGE_REVALUATION",
                            source_document_id=rev_id,
                        )
                    )
                    gl_entries.append(
                        GeneralLedgerEntry(
                            tenant_id=tenant_id,
                            transaction_id=tx_id,
                            posting_date=posting_date,
                            fiscal_year=posting_date.year,
                            fiscal_period=posting_date.month,
                            account_code=row.account_code,
                            cost_center="DEFAULT",
                            debit_amount=Decimal("0.0000"),
                            credit_amount=abs_diff,
                            currency=base_currency,
                            exchange_rate=Decimal("1.000000"),
                            source_document_type="EXCHANGE_REVALUATION",
                            source_document_id=rev_id,
                        )
                    )

        for e in gl_entries:
            session.add(e)

        reval = ExchangeRateRevaluation(
            tenant_id=tenant_id,
            revaluation_id=rev_id,
            revaluation_number=rev_number,
            posting_date=posting_date,
            total_gain_loss=total_gain_loss,
            journal_entry_id=tx_id if gl_entries else None,
            notes=notes,
        )
        session.add(reval)
        await session.flush()
        return reval

    async def list_revaluations(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> List[ExchangeRateRevaluation]:
        """Lists past FX revaluations."""
        stmt = (
            select(ExchangeRateRevaluation)
            .where(ExchangeRateRevaluation.tenant_id == tenant_id)
            .order_by(ExchangeRateRevaluation.posting_date.desc())
        )
        return list((await session.execute(stmt)).scalars().all())


exchange_service = ExchangeService()
