"""Seed standard Chart of Accounts and Cost Centers for Default Tenant."""

import asyncio
from datetime import date

from sqlalchemy import select

from erp.config import settings
from erp.db.models.ledger import Account, CostCenter, FiscalPeriod
from erp.db.session import async_session_factory

DEFAULT_ACCOUNTS = [
    # Assets
    ("1010-CASH", "Operating Cash", "ASSET", None),
    ("1020-BANK-OPERATING", "Operating Bank Account", "ASSET", None),
    ("1200-AR-CUSTOMERS", "Accounts Receivable", "ASSET", None),
    ("1300-RAW-MATERIALS", "Raw Materials Inventory", "ASSET", None),
    ("1350-FINISHED-GOODS", "Finished Goods Inventory", "ASSET", None),
    # Liabilities
    ("2100-AP-VENDORS", "Accounts Payable", "LIABILITY", None),
    ("2200-ACCRUED-EXPENSES", "Accrued Liabilities", "LIABILITY", None),
    # Equity
    ("3000-COMMON-STOCK", "Common Stock", "EQUITY", None),
    ("3100-RETAINED-EARNINGS", "Retained Earnings", "EQUITY", None),
    # Revenue
    ("4000-SALES-REVENUE", "Gross Sales Revenue", "REVENUE", None),
    # Expenses
    ("5000-COGS-MATERIALS", "Cost of Goods Sold - Materials", "EXPENSE", None),
    ("5100-COGS-LABOR", "Cost of Goods Sold - Direct Labor", "EXPENSE", None),
    ("6100-MAINTENANCE", "Machine Maintenance & Repairs", "EXPENSE", None),
    ("6200-TRAVEL-MEALS", "Travel & Entertainment", "EXPENSE", None),
]

DEFAULT_COST_CENTERS = [
    ("CORP-FINANCE", "Corporate Finance & Treasury"),
    ("PLANT-01", "Main Production Plant 01"),
    ("PLANT-02", "Assembly Plant 02"),
    ("SALES-GLOBAL", "Global Commercial Sales"),
]


async def seed_data():
    tenant_id = settings.DEFAULT_TENANT_ID
    print(f"Seeding master financial data for tenant {tenant_id}...")

    async with async_session_factory() as session:
        # 1. Accounts
        for code, name, acc_type, parent in DEFAULT_ACCOUNTS:
            stmt = select(Account).where(
                Account.tenant_id == tenant_id,
                Account.account_code == code,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                account = Account(
                    tenant_id=tenant_id,
                    account_code=code,
                    account_name=name,
                    account_type=acc_type,
                    currency="USD",
                    parent_account_code=parent,
                    is_active=True,
                )
                session.add(account)
                print(f"  + Added Account: {code} ({name})")

        # 2. Cost Centers
        for code, name in DEFAULT_COST_CENTERS:
            stmt = select(CostCenter).where(
                CostCenter.tenant_id == tenant_id,
                CostCenter.cost_center_code == code,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                cc = CostCenter(
                    tenant_id=tenant_id,
                    cost_center_code=code,
                    cost_center_name=name,
                    is_active=True,
                )
                session.add(cc)
                print(f"  + Added Cost Center: {code} ({name})")

        # 3. Fiscal Periods for 2026
        for period in range(1, 13):
            start_d = date(2026, period, 1)
            # end date calculation
            if period == 12:
                end_d = date(2026, 12, 31)
            else:
                end_d = date(2026, period + 1, 1)

            stmt = select(FiscalPeriod).where(
                FiscalPeriod.tenant_id == tenant_id,
                FiscalPeriod.fiscal_year == 2026,
                FiscalPeriod.fiscal_period == period,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                fp = FiscalPeriod(
                    tenant_id=tenant_id,
                    fiscal_year=2026,
                    fiscal_period=period,
                    start_date=start_d,
                    end_date=end_d,
                    is_locked=False,
                )
                session.add(fp)

        await session.commit()
        print("Master financial data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
