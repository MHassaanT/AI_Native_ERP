"""Multi-Company Group Consolidation and Inter-Company Accounting Service."""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.companies import Company, InterCompanyTransaction
from erp.db.models.ledger import GeneralLedgerEntry

logger = logging.getLogger(__name__)


class CompanyService:
    """Core domain service managing enterprise entity structures and consolidated trial balance."""

    async def create_company(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        company_name: str,
        company_code: str,
        default_currency: str = "USD",
        parent_company_id: Optional[uuid.UUID] = None,
        is_group: bool = False,
        tax_id: Optional[str] = None,
    ) -> Company:
        """Creates a legal company entity or consolidated holding group."""
        comp = Company(
            tenant_id=tenant_id,
            company_name=company_name,
            company_code=company_code.upper().strip(),
            default_currency=default_currency.upper().strip(),
            parent_company_id=parent_company_id,
            is_group=is_group,
            tax_id=tax_id,
            is_active=True,
        )
        session.add(comp)
        await session.flush()
        return comp

    async def list_companies(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> List[Company]:
        """Lists all companies within tenant."""
        stmt = (
            select(Company)
            .options(selectinload(Company.subsidiaries))
            .where(Company.tenant_id == tenant_id)
            .order_by(Company.company_name.asc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def record_inter_company_transaction(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_company_id: uuid.UUID,
        to_company_id: uuid.UUID,
        amount: Decimal,
        transaction_type: str,
        currency: str = "USD",
        reference_voucher_type: Optional[str] = None,
        reference_voucher_id: Optional[uuid.UUID] = None,
        transaction_date: Optional[date] = None,
    ) -> InterCompanyTransaction:
        """Records an intercompany balance movement for subsequent elimination."""
        if not transaction_date:
            transaction_date = date.today()

        tx = InterCompanyTransaction(
            tenant_id=tenant_id,
            from_company_id=from_company_id,
            to_company_id=to_company_id,
            transaction_date=transaction_date,
            transaction_type=transaction_type.upper(),
            amount=amount,
            currency=currency.upper(),
            reference_voucher_type=reference_voucher_type,
            reference_voucher_id=reference_voucher_id,
            is_eliminated=False,
        )
        session.add(tx)
        await session.flush()
        return tx

    async def list_inter_company_transactions(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        is_eliminated: Optional[bool] = None,
    ) -> List[InterCompanyTransaction]:
        """Lists intercompany transactions."""
        stmt = (
            select(InterCompanyTransaction)
            .options(
                selectinload(InterCompanyTransaction.from_company),
                selectinload(InterCompanyTransaction.to_company),
            )
            .where(InterCompanyTransaction.tenant_id == tenant_id)
        )
        if is_eliminated is not None:
            stmt = stmt.where(InterCompanyTransaction.is_eliminated == is_eliminated)
        stmt = stmt.order_by(InterCompanyTransaction.transaction_date.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_consolidated_trial_balance(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
    ) -> Dict[str, Any]:
        """
        Consolidates Trial Balance across parent and subsidiaries,
        performing automated elimination of internal inter-company balances.
        """
        from erp.workflows.reports.financial_reports_service import financial_reports_service

        base_tb = await financial_reports_service.get_trial_balance(
            session, tenant_id, from_date, to_date
        )

        # Inter-company transactions needing elimination
        ic_stmt = select(InterCompanyTransaction).where(
            InterCompanyTransaction.tenant_id == tenant_id,
            InterCompanyTransaction.transaction_date >= from_date,
            InterCompanyTransaction.transaction_date <= to_date,
        )
        ic_txs = (await session.execute(ic_stmt)).scalars().all()

        eliminated_total = sum((tx.amount for tx in ic_txs), Decimal("0.0000"))

        # Mark them as eliminated in memory/status
        elimination_adjustments: List[Dict[str, Any]] = []
        for tx in ic_txs:
            elimination_adjustments.append({
                "transaction_id": str(tx.transaction_id),
                "from_company_id": str(tx.from_company_id),
                "to_company_id": str(tx.to_company_id),
                "type": tx.transaction_type,
                "amount": tx.amount,
                "currency": tx.currency,
            })

        consolidated_totals = dict(base_tb["totals"])
        # Both sides of inter-company transaction get eliminated equally
        consolidated_totals["intercompany_elimination"] = eliminated_total
        consolidated_totals["consolidated_closing_debit"] = max(
            consolidated_totals["closing_debit"] - eliminated_total, Decimal("0.0000")
        )
        consolidated_totals["consolidated_closing_credit"] = max(
            consolidated_totals["closing_credit"] - eliminated_total, Decimal("0.0000")
        )
        consolidated_totals["is_consolidated_balanced"] = (
            consolidated_totals["consolidated_closing_debit"] == consolidated_totals["consolidated_closing_credit"]
        )

        return {
            "from_date": from_date,
            "to_date": to_date,
            "base_trial_balance": base_tb,
            "eliminations": elimination_adjustments,
            "consolidated_totals": consolidated_totals,
        }


company_service = CompanyService()
