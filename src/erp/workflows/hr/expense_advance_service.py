"""Employee Advances, Loans, and Expense Claim Reimbursement Domain Service."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.hr import ExpenseClaim
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.payroll import EmployeeAdvance


class ExpenseAdvanceService:
    """Manages employee cash advances, loan disbursements, and expense claim GL reimbursements."""

    async def create_employee_advance(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        advance_amount: Decimal,
        purpose: str,
        monthly_deduction_amount: Decimal,
        posting_date: date | None = None,
    ) -> EmployeeAdvance:
        adv_num = f"ADV-{date.today().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        advance = EmployeeAdvance(
            tenant_id=tenant_id,
            advance_number=adv_num,
            employee_id=employee_id,
            posting_date=posting_date or date.today(),
            advance_amount=advance_amount,
            purpose=purpose,
            monthly_deduction_amount=monthly_deduction_amount,
            repaid_amount=Decimal("0.0000"),
            status="PENDING",
        )
        db.add(advance)
        await db.flush()
        return advance

    async def approve_and_disburse_advance(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        advance_id: uuid.UUID,
        bank_account_code: str = "1020-BANK-OPERATING",
    ) -> EmployeeAdvance:
        stmt = select(EmployeeAdvance).where(
            EmployeeAdvance.tenant_id == tenant_id,
            EmployeeAdvance.advance_id == advance_id,
        )
        adv = (await db.execute(stmt)).scalar_one_or_none()
        if not adv:
            raise ValueError(f"EmployeeAdvance {advance_id} not found.")

        if adv.status != "PENDING":
            raise ValueError(f"Advance {adv.advance_number} is already {adv.status}.")

        adv.status = "PAID"
        txn_id = uuid.uuid4()
        fiscal_year = adv.posting_date.year
        fiscal_period = adv.posting_date.month

        # Debit: Employee Advance Clearing (Asset)
        debit_entry = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=txn_id,
            posting_date=adv.posting_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            account_code="1250-EMPLOYEE-ADVANCE-CLEARING",
            cost_center="DEFAULT",
            debit_amount=adv.advance_amount,
            credit_amount=Decimal("0.0000"),
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="EMPLOYEE_ADVANCE",
            source_document_id=adv.advance_id,
        )
        # Credit: Operating Bank
        credit_entry = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=txn_id,
            posting_date=adv.posting_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            account_code=bank_account_code,
            cost_center="DEFAULT",
            debit_amount=Decimal("0.0000"),
            credit_amount=adv.advance_amount,
            currency="USD",
            exchange_rate=Decimal("1.000000"),
            source_document_type="EMPLOYEE_ADVANCE",
            source_document_id=adv.advance_id,
        )
        db.add_all([debit_entry, credit_entry])
        await db.flush()
        return adv

    async def list_employee_advances(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[EmployeeAdvance]:
        stmt = select(EmployeeAdvance).where(EmployeeAdvance.tenant_id == tenant_id)
        if employee_id:
            stmt = stmt.where(EmployeeAdvance.employee_id == employee_id)
        if status:
            stmt = stmt.where(EmployeeAdvance.status == status)
        stmt = stmt.order_by(EmployeeAdvance.posting_date.desc())
        return list((await db.execute(stmt)).scalars().all())

    async def reimburse_expense_claim(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        bank_account_code: str = "1020-BANK-OPERATING",
    ) -> ExpenseClaim:
        stmt = select(ExpenseClaim).where(
            ExpenseClaim.tenant_id == tenant_id,
            ExpenseClaim.claim_id == claim_id,
        )
        claim = (await db.execute(stmt)).scalar_one_or_none()
        if not claim:
            raise ValueError(f"ExpenseClaim {claim_id} not found.")

        if claim.status in ["PAID", "REJECTED"]:
            raise ValueError(f"Claim {claim.claim_number} is already {claim.status}.")

        claim.status = "PAID"
        txn_id = uuid.uuid4()
        fiscal_year = claim.claim_date.year
        fiscal_period = claim.claim_date.month

        expense_acc = (
            "6200-TRAVEL-EXPENSE"
            if claim.category in ["LODGING", "TRANSPORT"]
            else "6210-MEALS-ENTERTAINMENT"
            if claim.category == "MEALS"
            else "6220-OFFICE-SUPPLIES"
        )

        debit_entry = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=txn_id,
            posting_date=claim.claim_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            account_code=expense_acc,
            cost_center="DEFAULT",
            debit_amount=claim.total_amount,
            credit_amount=Decimal("0.0000"),
            currency=claim.currency,
            exchange_rate=Decimal("1.000000"),
            source_document_type="EXPENSE_CLAIM",
            source_document_id=claim.claim_id,
        )
        credit_entry = GeneralLedgerEntry(
            tenant_id=tenant_id,
            transaction_id=txn_id,
            posting_date=claim.claim_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            account_code=bank_account_code,
            cost_center="DEFAULT",
            debit_amount=Decimal("0.0000"),
            credit_amount=claim.total_amount,
            currency=claim.currency,
            exchange_rate=Decimal("1.000000"),
            source_document_type="EXPENSE_CLAIM",
            source_document_id=claim.claim_id,
        )
        db.add_all([debit_entry, credit_entry])
        await db.flush()
        return claim


expense_advance_service = ExpenseAdvanceService()
