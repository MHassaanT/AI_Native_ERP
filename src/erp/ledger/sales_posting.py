"""Resolve tenant-owned ledger accounts for sales invoice posting."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.ledger import Account, CostCenter


class SalesPostingConfigurationError(ValueError):
    """Raised when tenant ledger configuration is missing or ambiguous."""


async def resolve_sales_posting_configuration(
    session: AsyncSession, tenant_id: uuid.UUID, currency: str
) -> tuple[Account, Account, CostCenter]:
    """Return unique tenant-owned AR, sales revenue, and cost center records."""
    ar_accounts = (
        await session.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.is_active.is_(True),
                Account.currency == currency,
                func.upper(Account.account_type).in_(("ASSET", "RECEIVABLE")),
                or_(
                    Account.account_name.ilike("%receivable%"),
                    Account.account_code.ilike("%AR%"),
                ),
            )
        )
    ).scalars().all()
    revenue_accounts = (
        await session.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.is_active.is_(True),
                Account.currency == currency,
                func.upper(Account.account_type) == "REVENUE",
                or_(
                    Account.account_name.ilike("%sales%"),
                    Account.account_name.ilike("%revenue%"),
                    Account.account_code.ilike("%REV%"),
                ),
            )
        )
    ).scalars().all()
    cost_centers = (
        await session.execute(
            select(CostCenter).where(
                CostCenter.tenant_id == tenant_id,
                CostCenter.is_active.is_(True),
            )
        )
    ).scalars().all()
    if len(ar_accounts) != 1 or len(revenue_accounts) != 1 or len(cost_centers) != 1:
        raise SalesPostingConfigurationError(
            "Sales posting requires exactly one active receivables account, one sales revenue account "
            "in the tenant currency, and one active cost center. Configure unambiguous tenant mappings first."
        )
    return ar_accounts[0], revenue_accounts[0], cost_centers[0]
