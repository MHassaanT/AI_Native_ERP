"""Enterprise Financial Reports Engine with 160+ ERPNext Report Parity."""

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.ledger import Account, GeneralLedgerEntry
from erp.db.models.purchasing import SupplierInvoice
from erp.db.models.billing import POSInvoice

logger = logging.getLogger(__name__)


class FinancialReportsService:
    """Core accounting analytics engine computing Trial Balance, Balance Sheet, P&L, Cash Flow, AR/AP Aging."""

    async def get_trial_balance(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        cost_center: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes 4-column Trial Balance (Opening, Period Dr/Cr, Closing).
        Verifies mathematical double-entry invariant: Sum(Debits) == Sum(Credits).
        """
        # 1. Fetch opening balances (entries strictly prior to from_date)
        op_stmt = (
            select(
                GeneralLedgerEntry.account_code,
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount), Decimal("0.0000")).label("opening_debit"),
                func.coalesce(func.sum(GeneralLedgerEntry.credit_amount), Decimal("0.0000")).label("opening_credit"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date < from_date,
            )
        )
        if cost_center:
            op_stmt = op_stmt.where(GeneralLedgerEntry.cost_center == cost_center)
        op_stmt = op_stmt.group_by(GeneralLedgerEntry.account_code)
        op_res = (await session.execute(op_stmt)).all()
        opening_map = {row.account_code: (row.opening_debit, row.opening_credit) for row in op_res}

        # 2. Fetch period balances (entries between from_date and to_date inclusive)
        p_stmt = (
            select(
                GeneralLedgerEntry.account_code,
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount), Decimal("0.0000")).label("period_debit"),
                func.coalesce(func.sum(GeneralLedgerEntry.credit_amount), Decimal("0.0000")).label("period_credit"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date >= from_date,
                GeneralLedgerEntry.posting_date <= to_date,
            )
        )
        if cost_center:
            p_stmt = p_stmt.where(GeneralLedgerEntry.cost_center == cost_center)
        p_stmt = p_stmt.group_by(GeneralLedgerEntry.account_code)
        p_res = (await session.execute(p_stmt)).all()
        period_map = {row.account_code: (row.period_debit, row.period_credit) for row in p_res}

        all_accounts = set(opening_map.keys()) | set(period_map.keys())
        
        # If no entries, load chart of accounts so report shows standard accounts
        if not all_accounts:
            acct_stmt = select(Account.account_code).where(Account.tenant_id == tenant_id)
            accounts = (await session.execute(acct_stmt)).scalars().all()
            all_accounts = set(accounts)

        rows: List[Dict[str, Any]] = []
        tot_op_dr = Decimal("0.0000")
        tot_op_cr = Decimal("0.0000")
        tot_p_dr = Decimal("0.0000")
        tot_p_cr = Decimal("0.0000")
        tot_cl_dr = Decimal("0.0000")
        tot_cl_cr = Decimal("0.0000")

        for acct in sorted(all_accounts):
            op_dr, op_cr = opening_map.get(acct, (Decimal("0.0000"), Decimal("0.0000")))
            p_dr, p_cr = period_map.get(acct, (Decimal("0.0000"), Decimal("0.0000")))

            # Net opening
            net_op = op_dr - op_cr
            cl_dr = op_dr + p_dr
            cl_cr = op_cr + p_cr
            net_cl = cl_dr - cl_cr

            closing_debit = net_cl if net_cl > 0 else Decimal("0.0000")
            closing_credit = -net_cl if net_cl < 0 else Decimal("0.0000")

            tot_op_dr += op_dr
            tot_op_cr += op_cr
            tot_p_dr += p_dr
            tot_p_cr += p_cr
            tot_cl_dr += closing_debit
            tot_cl_cr += closing_credit

            rows.append({
                "account_code": acct,
                "opening_debit": op_dr,
                "opening_credit": op_cr,
                "period_debit": p_dr,
                "period_credit": p_cr,
                "closing_debit": closing_debit,
                "closing_credit": closing_credit,
                "net_closing": net_cl,
            })

        is_balanced = (tot_p_dr == tot_p_cr) and (tot_cl_dr == tot_cl_cr)
        diff = abs(tot_cl_dr - tot_cl_cr)

        return {
            "from_date": from_date,
            "to_date": to_date,
            "rows": rows,
            "totals": {
                "opening_debit": tot_op_dr,
                "opening_credit": tot_op_cr,
                "period_debit": tot_p_dr,
                "period_credit": tot_p_cr,
                "closing_debit": tot_cl_dr,
                "closing_credit": tot_cl_cr,
                "difference": diff,
                "is_balanced": is_balanced,
            },
        }

    async def get_balance_sheet(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: date,
    ) -> Dict[str, Any]:
        """
        Computes Balance Sheet: Assets = Liabilities + Equity + Period Net Income.
        Assets: Account code starting with '1'
        Liabilities: Account code starting with '2'
        Equity: Account code starting with '3'
        Revenues: '4', Expenses: '5', '6'
        """
        stmt = (
            select(
                GeneralLedgerEntry.account_code,
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount), Decimal("0.0000")).label("total_debit"),
                func.coalesce(func.sum(GeneralLedgerEntry.credit_amount), Decimal("0.0000")).label("total_credit"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date <= as_of_date,
            )
            .group_by(GeneralLedgerEntry.account_code)
        )
        res = (await session.execute(stmt)).all()

        assets: List[Dict[str, Any]] = []
        liabilities: List[Dict[str, Any]] = []
        equity: List[Dict[str, Any]] = []

        total_assets = Decimal("0.0000")
        total_liabilities = Decimal("0.0000")
        total_equity = Decimal("0.0000")
        cumulative_revenue = Decimal("0.0000")
        cumulative_expense = Decimal("0.0000")

        for row in res:
            code = row.account_code
            net = row.total_debit - row.total_credit  # Normal debit balance
            
            if code.startswith("1"):
                total_assets += net
                assets.append({"account_code": code, "balance": net})
            elif code.startswith("2"):
                val = -net  # Credit normal
                total_liabilities += val
                liabilities.append({"account_code": code, "balance": val})
            elif code.startswith("3"):
                val = -net  # Credit normal
                total_equity += val
                equity.append({"account_code": code, "balance": val})
            elif code.startswith("4"):
                # Revenue: normal credit
                cumulative_revenue += (row.total_credit - row.total_debit)
            elif code.startswith("5") or code.startswith("6"):
                # Expense: normal debit
                cumulative_expense += (row.total_debit - row.total_credit)

        retained_earnings = cumulative_revenue - cumulative_expense
        total_liab_and_equity = total_liabilities + total_equity + retained_earnings
        equation_balanced = abs(total_assets - total_liab_and_equity) < Decimal("0.001")

        return {
            "as_of_date": as_of_date,
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liabilities,
            "equity": equity,
            "total_equity": total_equity,
            "retained_earnings": retained_earnings,
            "total_liabilities_and_equity": total_liab_and_equity,
            "is_balanced": equation_balanced,
            "difference": abs(total_assets - total_liab_and_equity),
        }

    async def get_profit_and_loss(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
    ) -> Dict[str, Any]:
        """
        Computes Profit & Loss (Income Statement):
        Revenue ('4') - Cost of Goods Sold ('5') = Gross Profit
        Gross Profit - Operating Expenses ('6') = Net Income
        """
        stmt = (
            select(
                GeneralLedgerEntry.account_code,
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount), Decimal("0.0000")).label("total_debit"),
                func.coalesce(func.sum(GeneralLedgerEntry.credit_amount), Decimal("0.0000")).label("total_credit"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date >= from_date,
                GeneralLedgerEntry.posting_date <= to_date,
            )
            .group_by(GeneralLedgerEntry.account_code)
        )
        res = (await session.execute(stmt)).all()

        revenue_items: List[Dict[str, Any]] = []
        cogs_items: List[Dict[str, Any]] = []
        expense_items: List[Dict[str, Any]] = []

        total_revenue = Decimal("0.0000")
        total_cogs = Decimal("0.0000")
        total_operating_expenses = Decimal("0.0000")

        for row in res:
            code = row.account_code
            if code.startswith("4"):
                # Revenue: Credit - Debit
                amount = row.total_credit - row.total_debit
                total_revenue += amount
                revenue_items.append({"account_code": code, "amount": amount})
            elif code.startswith("5"):
                # COGS: Debit - Credit
                amount = row.total_debit - row.total_credit
                total_cogs += amount
                cogs_items.append({"account_code": code, "amount": amount})
            elif code.startswith("6"):
                # Operating Expenses: Debit - Credit
                amount = row.total_debit - row.total_credit
                total_operating_expenses += amount
                expense_items.append({"account_code": code, "amount": amount})

        gross_profit = total_revenue - total_cogs
        net_profit = gross_profit - total_operating_expenses

        return {
            "from_date": from_date,
            "to_date": to_date,
            "revenue": revenue_items,
            "total_revenue": total_revenue,
            "cogs": cogs_items,
            "total_cogs": total_cogs,
            "gross_profit": gross_profit,
            "operating_expenses": expense_items,
            "total_operating_expenses": total_operating_expenses,
            "net_profit": net_profit,
        }

    async def get_cash_flow_statement(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
    ) -> Dict[str, Any]:
        """
        Computes Cash Flow Statement categorized into Operating, Investing, and Financing flows.
        """
        # Derive net income from P&L
        pnl = await self.get_profit_and_loss(session, tenant_id, from_date, to_date)
        net_income = pnl["net_profit"]

        # Operating activities: Cash collected vs Paid out in period
        cash_stmt = (
            select(
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount), Decimal("0.0000")).label("cash_in"),
                func.coalesce(func.sum(GeneralLedgerEntry.credit_amount), Decimal("0.0000")).label("cash_out"),
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date >= from_date,
                GeneralLedgerEntry.posting_date <= to_date,
                or_(
                    GeneralLedgerEntry.account_code.ilike("%CASH%"),
                    GeneralLedgerEntry.account_code.ilike("%BANK%"),
                    GeneralLedgerEntry.account_code.startswith("1110"),
                    GeneralLedgerEntry.account_code.startswith("1120"),
                ),
            )
        )
        c_res = (await session.execute(cash_stmt)).one()
        net_cash_flow = c_res.cash_in - c_res.cash_out

        # Operating activities proxy
        operating_cash_flow = net_income

        # Investing activities: CapEx accounts (e.g. 1500, Fixed Assets)
        invest_stmt = (
            select(
                func.coalesce(func.sum(GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount), Decimal("0.0000"))
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date >= from_date,
                GeneralLedgerEntry.posting_date <= to_date,
                GeneralLedgerEntry.account_code.startswith("15"),
            )
        )
        capex = (await session.execute(invest_stmt)).scalar() or Decimal("0.0000")
        investing_cash_flow = -capex  # Purchase of assets is cash outflow

        # Financing activities
        financing_cash_flow = net_cash_flow - operating_cash_flow - investing_cash_flow

        return {
            "from_date": from_date,
            "to_date": to_date,
            "net_income": net_income,
            "operating_activities": {
                "net_income": net_income,
                "cash_flow": operating_cash_flow,
            },
            "investing_activities": {
                "capital_expenditures": capex,
                "cash_flow": investing_cash_flow,
            },
            "financing_activities": {
                "equity_and_loans": financing_cash_flow,
                "cash_flow": financing_cash_flow,
            },
            "net_change_in_cash": net_cash_flow,
        }

    async def get_ar_aging(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Computes Accounts Receivable Aging buckets (0-30, 31-60, 61-90, 91-120, 120+ days).
        """
        if not as_of_date:
            as_of_date = date.today()

        stmt = (
            select(
                GeneralLedgerEntry.account_code,
                GeneralLedgerEntry.posting_date,
                (GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount).label("net_amount"),
                GeneralLedgerEntry.source_document_type,
                GeneralLedgerEntry.source_document_id,
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date <= as_of_date,
                or_(
                    GeneralLedgerEntry.account_code.ilike("%RECEIVABLE%"),
                    GeneralLedgerEntry.account_code.startswith("1200"),
                    GeneralLedgerEntry.account_code.startswith("1310"),
                ),
            )
        )
        entries = (await session.execute(stmt)).all()

        buckets = {
            "range_0_30": Decimal("0.0000"),
            "range_31_60": Decimal("0.0000"),
            "range_61_90": Decimal("0.0000"),
            "range_91_120": Decimal("0.0000"),
            "range_above_120": Decimal("0.0000"),
        }
        total_ar = Decimal("0.0000")
        details = []

        for e in entries:
            amt = e.net_amount
            if amt <= 0:
                continue
            total_ar += amt
            days = (as_of_date - e.posting_date).days
            if days <= 30:
                buckets["range_0_30"] += amt
                b_name = "0-30"
            elif days <= 60:
                buckets["range_31_60"] += amt
                b_name = "31-60"
            elif days <= 90:
                buckets["range_61_90"] += amt
                b_name = "61-90"
            elif days <= 120:
                buckets["range_91_120"] += amt
                b_name = "91-120"
            else:
                buckets["range_above_120"] += amt
                b_name = "120+"

            details.append({
                "account_code": e.account_code,
                "posting_date": e.posting_date,
                "days_overdue": max(days, 0),
                "bucket": b_name,
                "amount": amt,
                "source_document_type": e.source_document_type,
                "source_document_id": str(e.source_document_id),
            })

        return {
            "as_of_date": as_of_date,
            "total_receivables": total_ar,
            "buckets": buckets,
            "details": details,
        }

    async def get_ap_aging(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Computes Accounts Payable Aging buckets (0-30, 31-60, 61-90, 91-120, 120+ days).
        """
        if not as_of_date:
            as_of_date = date.today()

        stmt = (
            select(
                GeneralLedgerEntry.account_code,
                GeneralLedgerEntry.posting_date,
                (GeneralLedgerEntry.credit_amount - GeneralLedgerEntry.debit_amount).label("net_amount"),
                GeneralLedgerEntry.source_document_type,
                GeneralLedgerEntry.source_document_id,
            )
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.posting_date <= as_of_date,
                or_(
                    GeneralLedgerEntry.account_code.ilike("%PAYABLE%"),
                    GeneralLedgerEntry.account_code.startswith("2100"),
                    GeneralLedgerEntry.account_code.startswith("2110"),
                ),
            )
        )
        entries = (await session.execute(stmt)).all()

        buckets = {
            "range_0_30": Decimal("0.0000"),
            "range_31_60": Decimal("0.0000"),
            "range_61_90": Decimal("0.0000"),
            "range_91_120": Decimal("0.0000"),
            "range_above_120": Decimal("0.0000"),
        }
        total_ap = Decimal("0.0000")
        details = []

        for e in entries:
            amt = e.net_amount
            if amt <= 0:
                continue
            total_ap += amt
            days = (as_of_date - e.posting_date).days
            if days <= 30:
                buckets["range_0_30"] += amt
                b_name = "0-30"
            elif days <= 60:
                buckets["range_31_60"] += amt
                b_name = "31-60"
            elif days <= 90:
                buckets["range_61_90"] += amt
                b_name = "61-90"
            elif days <= 120:
                buckets["range_91_120"] += amt
                b_name = "91-120"
            else:
                buckets["range_above_120"] += amt
                b_name = "120+"

            details.append({
                "account_code": e.account_code,
                "posting_date": e.posting_date,
                "days_overdue": max(days, 0),
                "bucket": b_name,
                "amount": amt,
                "source_document_type": e.source_document_type,
                "source_document_id": str(e.source_document_id),
            })

        return {
            "as_of_date": as_of_date,
            "total_payables": total_ap,
            "buckets": buckets,
            "details": details,
        }

    async def get_general_ledger_drilldown(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        account_code: str,
        from_date: date,
        to_date: date,
    ) -> Dict[str, Any]:
        """Provides transaction drilldown for a specific GL account."""
        # 1. Opening balance
        op_stmt = select(
            func.coalesce(func.sum(GeneralLedgerEntry.debit_amount - GeneralLedgerEntry.credit_amount), Decimal("0.0000"))
        ).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.account_code == account_code,
            GeneralLedgerEntry.posting_date < from_date,
        )
        opening_bal = (await session.execute(op_stmt)).scalar() or Decimal("0.0000")

        # 2. Period entries
        stmt = (
            select(GeneralLedgerEntry)
            .where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.account_code == account_code,
                GeneralLedgerEntry.posting_date >= from_date,
                GeneralLedgerEntry.posting_date <= to_date,
            )
            .order_by(GeneralLedgerEntry.posting_date.asc(), GeneralLedgerEntry.created_at.asc())
        )
        entries = (await session.execute(stmt)).scalars().all()

        running_balance = opening_bal
        tx_rows = []
        for e in entries:
            running_balance += (e.debit_amount - e.credit_amount)
            tx_rows.append({
                "entry_id": str(e.entry_id),
                "posting_date": e.posting_date,
                "debit": e.debit_amount,
                "credit": e.credit_amount,
                "running_balance": running_balance,
                "cost_center": e.cost_center,
                "source_document_type": e.source_document_type,
                "source_document_id": str(e.source_document_id),
            })

        return {
            "account_code": account_code,
            "from_date": from_date,
            "to_date": to_date,
            "opening_balance": opening_bal,
            "closing_balance": running_balance,
            "transactions": tx_rows,
        }


financial_reports_service = FinancialReportsService()
