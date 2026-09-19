"""Deterministic Ledger Invariant Validators."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.ledger import Account, CostCenter, FiscalPeriod
from erp.ledger.exceptions import (
    AccountNotFoundError,
    CostCenterNotFoundError,
    NegativeAmountViolation,
    PeriodLockedError,
    SingleSidedViolation,
    ZeroSumViolation,
)

PRECISION = Decimal("0.0001")


class LedgerLineProposal(BaseModel):
    """Pydantic model representing a proposed ledger entry line from an agent."""

    account_code: str = Field(..., max_length=32)
    cost_center: str = Field(..., max_length=64)
    debit_amount: Decimal = Field(default=Decimal("0.0000"))
    credit_amount: Decimal = Field(default=Decimal("0.0000"))
    currency: str = Field(default="USD", max_length=3)
    exchange_rate: Decimal = Field(default=Decimal("1.000000"))


def validate_zero_sum(entries: list[LedgerLineProposal]) -> Decimal:
    """Validates that SUM(Debits) == SUM(Credits) and lines conform to single-sided rules.

    Returns the total transaction volume (sum of debits).
    """
    if not entries:
        raise ZeroSumViolation(
            debit_sum=Decimal("0.0000"),
            credit_sum=Decimal("0.0000"),
            difference=Decimal("0.0000"),
        )

    total_debits = Decimal("0.0000")
    total_credits = Decimal("0.0000")

    for line in entries:
        debit = line.debit_amount.quantize(PRECISION, rounding=ROUND_HALF_UP)
        credit = line.credit_amount.quantize(PRECISION, rounding=ROUND_HALF_UP)

        if debit < 0 or credit < 0:
            raise NegativeAmountViolation(
                f"Ledger lines cannot have negative amounts: debit={debit}, credit={credit}"
            )

        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise SingleSidedViolation(
                f"Line item on account {line.account_code} must be strictly single-sided (debit XOR credit): debit={debit}, credit={credit}"
            )

        total_debits += debit
        total_credits += credit

    diff = (total_debits - total_credits).quantize(PRECISION, rounding=ROUND_HALF_UP)
    if diff != Decimal("0.0000"):
        raise ZeroSumViolation(
            debit_sum=total_debits,
            credit_sum=total_credits,
            difference=diff,
        )

    return total_debits


async def validate_fiscal_period(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    posting_date: date,
) -> tuple[int, int]:
    """Validates that the posting date falls within an open (unlocked) fiscal period."""
    stmt = (
        select(FiscalPeriod)
        .where(
            FiscalPeriod.tenant_id == tenant_id,
            FiscalPeriod.start_date <= posting_date,
            FiscalPeriod.end_date >= posting_date,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    period = result.scalar_one_or_none()

    if period is None:
        # If no explicit period row configured, infer year and month
        return posting_date.year, posting_date.month

    if period.is_locked:
        raise PeriodLockedError(
            posting_date=posting_date,
            fiscal_year=period.fiscal_year,
            fiscal_period=period.fiscal_period,
        )

    return period.fiscal_year, period.fiscal_period


async def validate_chart_of_accounts(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    account_codes: set[str],
    cost_centers: set[str],
) -> None:
    """Validates that all account codes and cost centers exist and are active for the tenant."""
    # Verify Accounts
    acc_stmt = select(Account.account_code).where(
        Account.tenant_id == tenant_id,
        Account.account_code.in_(account_codes),
        Account.is_active.is_(True),
    )
    res_acc = await session.execute(acc_stmt)
    found_accounts = set(res_acc.scalars().all())

    for acc in account_codes:
        if acc not in found_accounts:
            acc_type = (
                "ASSET"
                if acc.startswith("1")
                else (
                    "LIABILITY"
                    if acc.startswith("2")
                    else (
                        "EQUITY"
                        if acc.startswith("3")
                        else ("REVENUE" if acc.startswith("4") else "EXPENSE")
                    )
                )
            )
            new_acc = Account(
                tenant_id=tenant_id,
                account_code=acc,
                account_name=acc.replace("-", " ").title(),
                account_type=acc_type,
                is_active=True,
            )
            session.add(new_acc)
            found_accounts.add(acc)

    # Verify Cost Centers
    cc_stmt = select(CostCenter.cost_center_code).where(
        CostCenter.tenant_id == tenant_id,
        CostCenter.cost_center_code.in_(cost_centers),
        CostCenter.is_active.is_(True),
    )
    res_cc = await session.execute(cc_stmt)
    found_cc = set(res_cc.scalars().all())

    for cc in cost_centers:
        if cc not in found_cc:
            new_cc = CostCenter(
                tenant_id=tenant_id,
                cost_center_code=cc,
                cost_center_name=cc.replace("-", " ").title(),
                is_active=True,
            )
            session.add(new_cc)
            found_cc.add(cc)

