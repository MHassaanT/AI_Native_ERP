"""Batch Payroll Entry Domain Service."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.hr import Employee
from erp.db.models.payroll import PayrollEntry, SalarySlip, SalaryStructureAssignment
from erp.workflows.payroll.payroll_service import payroll_service


class BatchPayrollService:
    """Manages company-wide or department-wide batch payroll processing."""

    async def create_batch_payroll(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        posting_date: date,
        start_date: date,
        end_date: date,
        department_id: uuid.UUID | None = None,
    ) -> tuple[PayrollEntry, list[SalarySlip]]:
        # Query active employees with assignments
        stmt = (
            select(Employee)
            .join(
                SalaryStructureAssignment,
                Employee.employee_id == SalaryStructureAssignment.employee_id,
            )
            .where(
                Employee.tenant_id == tenant_id,
                Employee.status == "ACTIVE",
                SalaryStructureAssignment.is_active.is_(True),
                SalaryStructureAssignment.from_date <= posting_date,
            )
            .distinct()
        )
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)

        employees = list((await db.execute(stmt)).scalars().all())
        if not employees:
            raise ValueError("No active employees with valid salary structures found for batch payroll.")

        payroll_num = f"PAY-{posting_date.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        payroll_entry = PayrollEntry(
            tenant_id=tenant_id,
            payroll_number=payroll_num,
            posting_date=posting_date,
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            payment_account_code="2100-PAYROLL-PAYABLE",
            expense_account_code="6100-SALARY-EXPENSE",
            status="DRAFT",
            total_gross_pay=Decimal("0.0000"),
            total_net_pay=Decimal("0.0000"),
        )
        db.add(payroll_entry)
        await db.flush()

        slips: list[SalarySlip] = []
        tot_gross = Decimal("0.0000")
        tot_net = Decimal("0.0000")

        for emp in employees:
            slip = await payroll_service.generate_salary_slip(
                db=db,
                tenant_id=tenant_id,
                employee_id=emp.employee_id,
                posting_date=posting_date,
                start_date=start_date,
                end_date=end_date,
            )
            slips.append(slip)
            tot_gross += slip.gross_pay
            tot_net += slip.net_pay

        payroll_entry.total_gross_pay = tot_gross
        payroll_entry.total_net_pay = tot_net
        await db.flush()
        return payroll_entry, slips

    async def submit_batch_payroll(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payroll_entry_id: uuid.UUID,
    ) -> PayrollEntry:
        stmt = select(PayrollEntry).where(
            PayrollEntry.tenant_id == tenant_id,
            PayrollEntry.payroll_entry_id == payroll_entry_id,
        )
        entry = (await db.execute(stmt)).scalar_one_or_none()
        if not entry:
            raise ValueError(f"PayrollEntry {payroll_entry_id} not found.")

        if entry.status != "DRAFT":
            raise ValueError(f"PayrollEntry {entry.payroll_number} is already {entry.status}.")

        # Find all draft salary slips for this period and tenant
        slips_stmt = (
            select(SalarySlip)
            .where(
                SalarySlip.tenant_id == tenant_id,
                SalarySlip.posting_date == entry.posting_date,
                SalarySlip.start_date == entry.start_date,
                SalarySlip.end_date == entry.end_date,
                SalarySlip.status == "DRAFT",
            )
        )
        slips = list((await db.execute(slips_stmt)).scalars().all())

        for s in slips:
            await payroll_service.submit_salary_slip(db, tenant_id, s.slip_id)

        entry.status = "SUBMITTED"
        await db.flush()
        return entry

    async def list_batch_payrolls(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[PayrollEntry]:
        stmt = (
            select(PayrollEntry)
            .where(PayrollEntry.tenant_id == tenant_id)
            .order_by(PayrollEntry.posting_date.desc())
        )
        return list((await db.execute(stmt)).scalars().all())


batch_payroll_service = BatchPayrollService()
