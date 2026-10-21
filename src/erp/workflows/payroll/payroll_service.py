"""Salary Components, Structure Assignment, Salary Slips, and GL Accounting Domain Service."""

import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.hr import Attendance, Employee, LeaveApplication, LeaveType
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.tenant import Tenant
from erp.db.models.currency import CurrencyExchangeRate
from erp.db.models.payroll import (
    AdditionalSalary,
    EmployeeAdvance,
    IncomeTaxSlab,
    PayrollPeriod,
    RetentionBonus,
    SalaryComponent,
    SalarySlip,
    SalarySlipItem,
    SalaryStructure,
    SalaryStructureAssignment,
    SalaryStructureItem,
)


def safe_eval_formula(formula: str, base: Decimal, gross: Decimal = Decimal("0.0")) -> Decimal:
    """Safely evaluates a arithmetic salary formula like 'base * 0.40' or 'gross * 0.05'."""
    clean = formula.replace("base", str(base)).replace("gross", str(gross)).strip()
    if not re.match(r"^[\d\.\s\+\-\*\/\(\)]+$", clean):
        raise ValueError(f"Invalid arithmetic expression in formula: {formula}")
    try:
        val = eval(clean, {"__builtins__": None}, {})  # noqa: S307
        return Decimal(str(round(val, 4)))
    except Exception as e:
        raise ValueError(f"Formula evaluation failed for '{formula}': {e}") from e


class PayrollService:
    """Manages compensation structures, salary slips, LWP calculations, and GL disbursement."""

    async def create_salary_component(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        component_name: str,
        component_code: str,
        component_type: str,  # EARNING, DEDUCTION
        calculation_type: str = "FIXED",  # FIXED, FORMULA
        formula_expression: str | None = None,
        is_taxable: bool = True,
        account_code: str = "6100-SALARY-EXPENSE",
    ) -> SalaryComponent:
        comp = SalaryComponent(
            tenant_id=tenant_id,
            component_name=component_name,
            component_code=component_code.upper().strip(),
            component_type=component_type,
            calculation_type=calculation_type,
            formula_expression=formula_expression,
            is_taxable=is_taxable,
            account_code=account_code,
            is_active=True,
        )
        db.add(comp)
        await db.flush()
        return comp

    async def list_salary_components(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[SalaryComponent]:
        stmt = (
            select(SalaryComponent)
            .where(SalaryComponent.tenant_id == tenant_id)
            .order_by(SalaryComponent.component_type.asc(), SalaryComponent.component_name.asc())
        )
        existing = list((await db.execute(stmt)).scalars().all())
        existing_codes = {c.component_code.upper() for c in existing}

        defaults = [
            ("Basic Salary", "BASIC", "EARNING", "FIXED", True, "6100-SALARY-EXPENSE"),
            ("House Rent Allowance", "HRA", "EARNING", "FIXED", True, "6100-SALARY-EXPENSE"),
            ("Income Tax Withholding", "TAX", "DEDUCTION", "FIXED", False, "2120-TAX-WITHHOLDING-PAYABLE"),
            ("Provident Fund / Pension", "PF", "DEDUCTION", "FIXED", False, "2130-BENEFITS-PAYABLE"),
        ]
        created_any = False
        for name, code, ctype, calc, taxable, acc in defaults:
            if code not in existing_codes:
                comp = SalaryComponent(
                    tenant_id=tenant_id,
                    component_name=name,
                    component_code=code,
                    component_type=ctype,
                    calculation_type=calc,
                    formula_expression=None,
                    is_taxable=taxable,
                    account_code=acc,
                    is_active=True,
                )
                db.add(comp)
                created_any = True

        if created_any:
            await db.flush()
            existing = list((await db.execute(stmt)).scalars().all())

        return existing

    async def create_salary_structure(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        structure_name: str,
        items: list[dict],
        payroll_frequency: str = "MONTHLY",
        currency: str = "USD",
    ) -> SalaryStructure:
        if not items:
            raise ValueError("Salary structure must include at least one component.")

        comp_ids = [uuid.UUID(str(itm["component_id"])) for itm in items]
        types_stmt = select(SalaryComponent.component_type).where(
            SalaryComponent.tenant_id == tenant_id,
            SalaryComponent.component_id.in_(comp_ids),
        )
        c_types = (await db.execute(types_stmt)).scalars().all()
        if "EARNING" not in c_types:
            raise ValueError("Salary structure must include at least one EARNING component (e.g. Basic Salary).")

        struct = SalaryStructure(
            tenant_id=tenant_id,
            structure_name=structure_name,
            payroll_frequency=payroll_frequency,
            currency=currency,
            is_active=True,
        )
        db.add(struct)
        await db.flush()

        for itm in items:
            s_item = SalaryStructureItem(
                tenant_id=tenant_id,
                structure_id=struct.structure_id,
                component_id=uuid.UUID(str(itm["component_id"])),
                amount=Decimal(str(itm.get("amount", "0.0000"))),
                formula_expression=itm.get("formula_expression"),
            )
            db.add(s_item)
        await db.flush()
        return struct

    async def list_salary_structures(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[SalaryStructure]:
        stmt = (
            select(SalaryStructure)
            .options(selectinload(SalaryStructure.items).selectinload(SalaryStructureItem.component))
            .where(SalaryStructure.tenant_id == tenant_id)
            .order_by(SalaryStructure.structure_name.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def assign_salary_structure(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        structure_id: uuid.UUID,
        from_date: date,
        base_salary: Decimal,
    ) -> SalaryStructureAssignment:
        assignment = SalaryStructureAssignment(
            tenant_id=tenant_id,
            employee_id=employee_id,
            structure_id=structure_id,
            from_date=from_date,
            base_salary=base_salary,
            is_active=True,
        )
        db.add(assignment)
        await db.flush()
        return assignment

    async def get_active_assignment(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        ref_date: date,
    ) -> SalaryStructureAssignment | None:
        stmt = (
            select(SalaryStructureAssignment)
            .options(
                selectinload(SalaryStructureAssignment.structure)
                .selectinload(SalaryStructure.items)
                .selectinload(SalaryStructureItem.component)
            )
            .where(
                SalaryStructureAssignment.tenant_id == tenant_id,
                SalaryStructureAssignment.employee_id == employee_id,
                SalaryStructureAssignment.from_date <= ref_date,
                SalaryStructureAssignment.is_active.is_(True),
            )
            .order_by(SalaryStructureAssignment.from_date.desc())
        )
        return (await db.execute(stmt)).scalars().first()

    async def generate_salary_slip(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        posting_date: date,
        start_date: date,
        end_date: date,
    ) -> SalarySlip:
        assignment = await self.get_active_assignment(db, tenant_id, employee_id, posting_date)
        if not assignment:
            raise ValueError(f"No active SalaryStructureAssignment found for employee {employee_id}.")

        total_calendar_days = (end_date - start_date).days + 1
        if total_calendar_days <= 0:
            raise ValueError("Payroll period end date must be on or after its start date.")
        total_working_days = total_calendar_days

        duplicate_stmt = select(SalarySlip.slip_id).where(
            SalarySlip.tenant_id == tenant_id,
            SalarySlip.employee_id == employee_id,
            SalarySlip.status != "CANCELLED",
            SalarySlip.start_date <= end_date,
            SalarySlip.end_date >= start_date,
        ).limit(1)
        if await db.scalar(duplicate_stmt):
            raise ValueError("An active salary slip already covers part or all of this payroll period.")

        # Calculate Leave Without Pay (LWP) days from Attendance (ABSENT) and approved LWP applications
        absent_stmt = select(func.count(Attendance.attendance_id)).where(
            Attendance.tenant_id == tenant_id,
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.status == "ABSENT",
        )
        absent_days = Decimal(str((await db.execute(absent_stmt)).scalar() or 0))

        # Check approved LWP leaves
        lwp_stmt = (
            select(LeaveApplication)
            .join(LeaveType, LeaveApplication.leave_type_id == LeaveType.leave_type_id)
            .where(
                LeaveApplication.tenant_id == tenant_id,
                LeaveApplication.employee_id == employee_id,
                LeaveApplication.status == "APPROVED",
                LeaveType.is_lwp.is_(True),
                LeaveApplication.from_date <= end_date,
                LeaveApplication.to_date >= start_date,
            )
        )
        lwp_applications = list((await db.execute(lwp_stmt)).scalars().all())
        lwp_app_days = Decimal("0.00")
        for leave in lwp_applications:
            overlap_start = max(start_date, leave.from_date)
            overlap_end = min(end_date, leave.to_date)
            overlap_days = Decimal((overlap_end - overlap_start).days + 1)
            leave_days = Decimal((leave.to_date - leave.from_date).days + 1)
            if leave_days > 0:
                lwp_app_days += min(leave.total_leave_days, leave_days) * overlap_days / leave_days

        leave_without_pay_days = absent_days + lwp_app_days
        payment_days = max(Decimal("0.00"), Decimal(str(total_working_days)) - leave_without_pay_days)
        pay_factor = payment_days / Decimal(str(total_working_days))

        base_salary = assignment.base_salary
        gross_pay = Decimal("0.0000")
        taxable_pay = Decimal("0.0000")
        recurring_taxable_pay = Decimal("0.0000")
        one_time_taxable_pay = Decimal("0.0000")
        total_deductions = Decimal("0.0000")
        slip_items_to_add: list[dict] = []

        # Process Earnings
        for item in assignment.structure.items:
            comp = item.component
            if comp.component_type == "EARNING":
                raw_amt = Decimal("0.0000")
                if comp.calculation_type == "FORMULA" and (item.formula_expression or comp.formula_expression):
                    formula = item.formula_expression or comp.formula_expression
                    raw_amt = safe_eval_formula(formula, base_salary, gross_pay)
                elif item.amount > 0:
                    raw_amt = item.amount
                else:
                    raw_amt = base_salary

                # Pro-rate by attendance/working days
                earned_amt = Decimal(str(round(raw_amt * pay_factor, 4)))
                gross_pay += earned_amt
                if comp.is_taxable:
                    taxable_pay += earned_amt
                    recurring_taxable_pay += earned_amt
                slip_items_to_add.append({
                    "component_id": comp.component_id,
                    "component_name": comp.component_name,
                    "component_type": "EARNING",
                    "amount": earned_amt,
                })

        # Apply pending one-time additions that are due in this pay period.
        additions_stmt = select(AdditionalSalary).where(
            AdditionalSalary.tenant_id == tenant_id,
            AdditionalSalary.employee_id == employee_id,
            AdditionalSalary.payroll_date >= start_date,
            AdditionalSalary.payroll_date <= end_date,
            AdditionalSalary.status == "PENDING",
        )
        additions = list((await db.execute(additions_stmt)).scalars().all())
        for addition in additions:
            if addition.component_type == "DEDUCTION":
                total_deductions += addition.amount
                line_type = "DEDUCTION"
            else:
                gross_pay += addition.amount
                line_type = "EARNING"
                if addition.is_taxable:
                    taxable_pay += addition.amount
                    one_time_taxable_pay += addition.amount
            slip_items_to_add.append({"component_id": addition.salary_component_id, "component_name": addition.component_name, "component_type": line_type, "amount": addition.amount, "source": addition})

        bonuses_stmt = select(RetentionBonus).where(
            RetentionBonus.tenant_id == tenant_id,
            RetentionBonus.employee_id == employee_id,
            RetentionBonus.vesting_date >= start_date,
            RetentionBonus.vesting_date <= end_date,
            RetentionBonus.status == "PENDING",
        )
        bonuses = list((await db.execute(bonuses_stmt)).scalars().all())
        for bonus in bonuses:
            gross_pay += bonus.amount
            if bonus.is_taxable:
                taxable_pay += bonus.amount
                one_time_taxable_pay += bonus.amount
            slip_items_to_add.append({"component_id": None, "component_name": bonus.bonus_name, "component_type": "EARNING", "amount": bonus.amount, "source": bonus})

        # Tax slabs are annual progressive brackets. Annualize recurring pay based on
        # the actual payroll period and withhold one period's liability. Tax one-time
        # taxable additions as the incremental annual liability they cause.
        tax_stmt = (
            select(IncomeTaxSlab)
            .options(selectinload(IncomeTaxSlab.rates))
            .where(IncomeTaxSlab.tenant_id == tenant_id, IncomeTaxSlab.is_active.is_(True),
                   IncomeTaxSlab.currency == assignment.structure.currency.upper(),
                   IncomeTaxSlab.effective_from <= posting_date, IncomeTaxSlab.effective_to >= posting_date)
            .order_by(IncomeTaxSlab.effective_from.desc())
        )
        tax_slab = (await db.execute(tax_stmt)).scalars().first()
        income_tax = Decimal("0.0000")
        if tax_slab and taxable_pay > 0:
            periods_per_year = Decimal("365.2425") / Decimal(total_calendar_days)
            recurring_annual_income = recurring_taxable_pay * periods_per_year

            def annual_tax_for(annual_income: Decimal) -> Decimal:
                band = max(
                    (rate for rate in tax_slab.rates if annual_income > rate.lower_bound),
                    key=lambda rate: rate.lower_bound,
                    default=None,
                )
                if band is None:
                    return Decimal("0")
                return band.fixed_amount + (annual_income - band.lower_bound) * band.tax_rate

            recurring_tax = annual_tax_for(recurring_annual_income) / periods_per_year
            one_time_tax = annual_tax_for(recurring_annual_income + one_time_taxable_pay) - annual_tax_for(recurring_annual_income)
            income_tax = (recurring_tax + one_time_tax).quantize(Decimal("0.0001"))
            total_deductions += income_tax
            slip_items_to_add.append({"component_id": None, "component_name": f"Income Tax Withholding ({tax_slab.tax_year})", "component_type": "DEDUCTION", "amount": income_tax})

        period_stmt = select(PayrollPeriod).where(
            PayrollPeriod.tenant_id == tenant_id,
            PayrollPeriod.start_date == start_date,
            PayrollPeriod.end_date == end_date,
        )
        payroll_period = (await db.execute(period_stmt)).scalars().first()
        if payroll_period and payroll_period.status != "OPEN":
            raise ValueError(f"Payroll period '{payroll_period.period_name}' is closed.")

        # Process Deductions
        for item in assignment.structure.items:
            comp = item.component
            if comp.component_type == "DEDUCTION":
                if tax_slab and comp.component_code.upper() in {"TAX", "INCOME-TAX", "INCOME_TAX"}:
                    continue
                ded_amt = Decimal("0.0000")
                if comp.calculation_type == "FORMULA" and (item.formula_expression or comp.formula_expression):
                    formula = item.formula_expression or comp.formula_expression
                    ded_amt = safe_eval_formula(formula, base_salary, gross_pay)
                else:
                    ded_amt = item.amount

                ded_amt = Decimal(str(round(ded_amt, 4)))
                total_deductions += ded_amt
                slip_items_to_add.append({
                    "component_id": comp.component_id,
                    "component_name": comp.component_name,
                    "component_type": "DEDUCTION",
                    "amount": ded_amt,
                })

        # Check for active employee advance with monthly recovery
        adv_stmt = (
            select(EmployeeAdvance)
            .where(
                EmployeeAdvance.tenant_id == tenant_id,
                EmployeeAdvance.employee_id == employee_id,
                EmployeeAdvance.status == "PAID",
                EmployeeAdvance.repaid_amount < EmployeeAdvance.advance_amount,
            )
            .order_by(EmployeeAdvance.posting_date.asc())
        )
        active_adv = (await db.execute(adv_stmt)).scalars().first()
        if active_adv and active_adv.monthly_deduction_amount > 0:
            remaining_debt = active_adv.advance_amount - active_adv.repaid_amount
            emi = min(active_adv.monthly_deduction_amount, remaining_debt)
            total_deductions += emi
            slip_items_to_add.append({
                "component_id": None,
                "component_name": f"Advance Recovery ({active_adv.advance_number})",
                "component_type": "DEDUCTION",
                "amount": emi,
            })

        net_pay = gross_pay - total_deductions

        slip_number = f"SLIP-{posting_date.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        slip = SalarySlip(
            tenant_id=tenant_id,
            slip_number=slip_number,
            employee_id=employee_id,
            posting_date=posting_date,
            start_date=start_date,
            end_date=end_date,
            currency=assignment.structure.currency.upper(),
            total_working_days=total_working_days,
            payment_days=payment_days,
            leave_without_pay_days=leave_without_pay_days,
            gross_pay=gross_pay,
            total_deductions=total_deductions,
            net_pay=net_pay,
            income_tax=income_tax,
            payroll_period_id=payroll_period.payroll_period_id if payroll_period else None,
            status="DRAFT",
        )
        db.add(slip)
        await db.flush()

        for s_item in slip_items_to_add:
            line = SalarySlipItem(
                tenant_id=tenant_id,
                slip_id=slip.slip_id,
                component_id=s_item["component_id"],
                component_name=s_item["component_name"],
                component_type=s_item["component_type"],
                amount=s_item["amount"],
            )
            db.add(line)
            source = s_item.get("source")
            if source:
                source.status = "EARNED" if isinstance(source, RetentionBonus) else "INCLUDED"
                source.slip_id = slip.slip_id
        await db.flush()
        return slip

    async def get_salary_slip(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        slip_id: uuid.UUID,
    ) -> SalarySlip | None:
        stmt = (
            select(SalarySlip)
            .options(selectinload(SalarySlip.items))
            .where(
                SalarySlip.tenant_id == tenant_id,
                SalarySlip.slip_id == slip_id,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def submit_salary_slip(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        slip_id: uuid.UUID,
    ) -> SalarySlip:
        slip = await self.get_salary_slip(db, tenant_id, slip_id)
        if not slip:
            raise ValueError(f"SalarySlip {slip_id} not found.")
        if slip.status != "DRAFT":
            raise ValueError(f"SalarySlip {slip.slip_number} is already {slip.status}.")

        if slip.gross_pay <= Decimal("0.0000"):
            raise ValueError(
                f"Cannot submit salary slip {slip.slip_number} to General Ledger: Gross Pay is ${slip.gross_pay:,.2f}. "
                "A valid salary slip must have gross earnings greater than zero. Please check employee salary structure earnings."
            )
        if slip.net_pay < Decimal("0.0000"):
            raise ValueError(
                f"Cannot submit salary slip {slip.slip_number} to General Ledger: Net Pay cannot be negative (${slip.net_pay:,.2f}). "
                f"Total deductions (${slip.total_deductions:,.2f}) cannot exceed gross pay (${slip.gross_pay:,.2f})."
            )

        txn_id = uuid.uuid4()
        fiscal_year = slip.posting_date.year
        fiscal_period = slip.posting_date.month
        tenant_currency = await db.scalar(select(Tenant.currency).where(Tenant.tenant_id == tenant_id))
        if not tenant_currency:
            raise ValueError("Tenant base currency is not configured.")
        tenant_currency = tenant_currency.upper()
        slip_currency = slip.currency.upper()
        exchange_rate = Decimal("1.000000")
        if slip_currency != tenant_currency:
            configured_rate = await db.scalar(select(CurrencyExchangeRate.exchange_rate).where(
                CurrencyExchangeRate.tenant_id == tenant_id,
                CurrencyExchangeRate.from_currency == slip_currency,
                CurrencyExchangeRate.to_currency == tenant_currency,
                CurrencyExchangeRate.effective_date <= slip.posting_date,
            ).order_by(CurrencyExchangeRate.effective_date.desc()).limit(1))
            if configured_rate is None:
                reciprocal = await db.scalar(select(CurrencyExchangeRate.exchange_rate).where(
                    CurrencyExchangeRate.tenant_id == tenant_id,
                    CurrencyExchangeRate.from_currency == tenant_currency,
                    CurrencyExchangeRate.to_currency == slip_currency,
                    CurrencyExchangeRate.effective_date <= slip.posting_date,
                ).order_by(CurrencyExchangeRate.effective_date.desc()).limit(1))
                if reciprocal is None or reciprocal <= 0:
                    raise ValueError(f"No exchange rate is configured for {slip_currency}/{tenant_currency} on {slip.posting_date}.")
                exchange_rate = Decimal("1") / reciprocal
            else:
                exchange_rate = configured_rate

        def base_amount(amount: Decimal) -> Decimal:
            return (amount * exchange_rate).quantize(Decimal("0.0001"))

        base_gross_pay = base_amount(slip.gross_pay)
        base_deductions = sum(
            (base_amount(item.amount) for item in slip.items if item.component_type == "DEDUCTION"),
            Decimal("0.0000"),
        )
        base_net_pay = base_gross_pay - base_deductions
        if base_net_pay < 0:
            raise ValueError("Rounded base-currency payroll deductions exceed gross pay.")

        # 1. Debit Salary Expense for Gross Pay (only if > 0)
        if slip.gross_pay > Decimal("0.0000"):
            debit_entry = GeneralLedgerEntry(
                tenant_id=tenant_id,
                transaction_id=txn_id,
                posting_date=slip.posting_date,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                account_code="6100-SALARY-EXPENSE",
                cost_center="DEFAULT",
                debit_amount=base_gross_pay,
                credit_amount=Decimal("0.0000"),
                currency=tenant_currency,
                exchange_rate=Decimal("1.000000"),
                source_document_type="SALARY_SLIP",
                source_document_id=slip.slip_id,
            )
            db.add(debit_entry)

        # 2. Credit Payroll Payable for Net Pay (only if > 0)
        if slip.net_pay > Decimal("0.0000"):
            credit_net = GeneralLedgerEntry(
                tenant_id=tenant_id,
                transaction_id=txn_id,
                posting_date=slip.posting_date,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                account_code="2100-PAYROLL-PAYABLE",
                cost_center="DEFAULT",
                debit_amount=Decimal("0.0000"),
                credit_amount=base_net_pay,
                currency=tenant_currency,
                exchange_rate=Decimal("1.000000"),
                source_document_type="SALARY_SLIP",
                source_document_id=slip.slip_id,
            )
            db.add(credit_net)

        # 3. Credit deduction liability accounts (only if > 0)
        for itm in slip.items:
            if itm.component_type == "DEDUCTION" and itm.amount > Decimal("0.0000"):
                acc = "2130-BENEFITS-PAYABLE"
                if "TAX" in itm.component_name.upper() or "TDS" in itm.component_name.upper():
                    acc = "2120-TAX-WITHHOLDING-PAYABLE"
                elif "ADVANCE" in itm.component_name.upper() or "LOAN" in itm.component_name.upper():
                    acc = "1250-EMPLOYEE-ADVANCE-CLEARING"
                    # Update advance repaid amount
                    adv_stmt = (
                        select(EmployeeAdvance)
                        .where(
                            EmployeeAdvance.tenant_id == tenant_id,
                            EmployeeAdvance.employee_id == slip.employee_id,
                            EmployeeAdvance.status == "PAID",
                            EmployeeAdvance.repaid_amount < EmployeeAdvance.advance_amount,
                        )
                        .order_by(EmployeeAdvance.posting_date.asc())
                    )
                    adv = (await db.execute(adv_stmt)).scalars().first()
                    if adv:
                        adv.repaid_amount += itm.amount
                        if adv.repaid_amount >= adv.advance_amount:
                            adv.status = "REPAID"

                credit_ded = GeneralLedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn_id,
                    posting_date=slip.posting_date,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    account_code=acc,
                    cost_center="DEFAULT",
                    debit_amount=Decimal("0.0000"),
                    credit_amount=base_amount(itm.amount),
                    currency=tenant_currency,
                    exchange_rate=Decimal("1.000000"),
                    source_document_type="SALARY_SLIP",
                    source_document_id=slip.slip_id,
                )
                db.add(credit_ded)

        slip.status = "SUBMITTED"
        slip.journal_entry_id = txn_id
        await db.flush()
        for model in (AdditionalSalary, RetentionBonus):
            stmt = select(model).where(model.tenant_id == tenant_id, model.slip_id == slip.slip_id)
            for source in (await db.execute(stmt)).scalars().all():
                source.status = "PAID"
        return slip

    async def list_salary_slips(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[SalarySlip]:
        stmt = (
            select(SalarySlip)
            .options(selectinload(SalarySlip.items))
            .where(SalarySlip.tenant_id == tenant_id)
        )
        if employee_id:
            stmt = stmt.where(SalarySlip.employee_id == employee_id)
        if status:
            stmt = stmt.where(SalarySlip.status == status)
        stmt = stmt.order_by(SalarySlip.posting_date.desc())
        return list((await db.execute(stmt)).scalars().all())


payroll_service = PayrollService()
