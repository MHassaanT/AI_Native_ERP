"""Financial Budgeting & Expenditure Control Service.

Tracks budget allocations per cost center / expense account,
evaluates real-time spending from the General Ledger, and enforces WARN / STOP constraints.
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.billing import Budget
from erp.db.models.ledger import GeneralLedgerEntry


class BudgetService:
    """Financial budget validator and allocator."""

    async def create_budget(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        budget_name: str,
        fiscal_year: int,
        cost_center: str,
        account_code: str,
        budget_amount: Decimal,
        action_on_exceed: str = "WARN",  # WARN, STOP, IGNORE
    ) -> Budget:
        """Sets a financial budget limit for a cost center and account."""
        budget = Budget(
            tenant_id=tenant_id,
            budget_name=budget_name,
            fiscal_year=fiscal_year,
            cost_center=cost_center,
            account_code=account_code,
            budget_amount=budget_amount,
            action_on_exceed=action_on_exceed.upper(),
            is_active=True,
        )
        session.add(budget)
        await session.flush()
        return budget

    async def evaluate_budget_compliance(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: int,
        cost_center: str,
        account_code: str,
        proposed_expense: Decimal,
    ) -> dict:
        """Evaluates whether proposed expenditure complies with configured budget thresholds."""
        stmt = select(Budget).where(
            Budget.tenant_id == tenant_id,
            Budget.fiscal_year == fiscal_year,
            Budget.cost_center == cost_center,
            Budget.account_code == account_code,
            Budget.is_active.is_(True),
        )
        res = await session.execute(stmt)
        budget = res.scalars().first()

        if not budget:
            return {
                "budget_configured": False,
                "status": "NO_BUDGET",
                "allowed": True,
                "message": "No budget restriction configured for this cost center/account.",
            }

        # Calculate historical posted debits for this account & cost center in the fiscal year
        spent_stmt = select(
            func.coalesce(func.sum(GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount), Decimal("0.0000"))
        ).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.fiscal_year == fiscal_year,
            GeneralLedgerEntry.cost_center == cost_center,
            GeneralLedgerEntry.account_code == account_code,
        )
        spent_res = await session.execute(spent_stmt)
        already_spent = spent_res.scalar_one()

        projected_total = already_spent + proposed_expense
        budget_limit = budget.budget_amount
        exceeded = projected_total > budget_limit
        excess_amount = max(Decimal("0.0000"), projected_total - budget_limit)

        if exceeded:
            if budget.action_on_exceed == "STOP":
                return {
                    "budget_configured": True,
                    "budget_name": budget.budget_name,
                    "budget_amount": float(budget_limit),
                    "already_spent": float(already_spent),
                    "proposed_expense": float(proposed_expense),
                    "projected_total": float(projected_total),
                    "excess_amount": float(excess_amount),
                    "action_on_exceed": "STOP",
                    "status": "STOP_BLOCKED",
                    "allowed": False,
                    "message": f"Expenditure exceeds budget by ${excess_amount:,.2f}. Action STOP prohibits booking.",
                }
            else:
                return {
                    "budget_configured": True,
                    "budget_name": budget.budget_name,
                    "budget_amount": float(budget_limit),
                    "already_spent": float(already_spent),
                    "proposed_expense": float(proposed_expense),
                    "projected_total": float(projected_total),
                    "excess_amount": float(excess_amount),
                    "action_on_exceed": "WARN",
                    "status": "WARNING_EXCEEDED",
                    "allowed": True,
                    "message": f"Warning: Expenditure exceeds budget limit by ${excess_amount:,.2f}.",
                }

        return {
            "budget_configured": True,
            "budget_name": budget.budget_name,
            "budget_amount": float(budget_limit),
            "already_spent": float(already_spent),
            "proposed_expense": float(proposed_expense),
            "projected_total": float(projected_total),
            "remaining_budget": float(budget_limit - projected_total),
            "action_on_exceed": budget.action_on_exceed,
            "status": "COMPLIANT",
            "allowed": True,
            "message": "Expenditure is fully within allocated budget.",
        }
