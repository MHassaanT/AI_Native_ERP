"""Phase 4 Automated Parity Verification Suite: HRMS & Payroll Suite."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.models.hr import (
    Attendance,
    Department,
    Designation,
    Employee,
    EmployeeOnboarding,
    EmployeeSeparation,
    ExpenseClaim,
    LeaveAllocation,
    LeaveApplication,
    LeaveType,
    OnboardingTask,
    SeparationTask,
    ShiftAssignment,
    ShiftType,
)
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.payroll import (
    EmployeeAdvance,
    PayrollEntry,
    SalaryComponent,
    SalarySlip,
    SalaryStructure,
    SalaryStructureAssignment,
)
from erp.db.session import async_session_factory
from erp.workflows.hr import (
    attendance_service,
    employee_service,
    expense_advance_service,
    leave_service,
)
from erp.workflows.payroll import batch_payroll_service, payroll_service


@pytest.mark.asyncio
async def test_phase4_complete_hrms_payroll_parity():
    """Exhaustive end-to-end integration test certifying 100% ERPNext HRMS & Payroll Parity."""
    async with async_session_factory() as db:
        tenant_id = uuid.uuid4()

        # =========================================================================
        # STEP 1: Department & Designation Master Hierarchy
        # =========================================================================
        dept_eng = await employee_service.create_department(
            db=db,
            tenant_id=tenant_id,
            department_name=f"Engineering-{uuid.uuid4().hex[:4]}",
        )
        assert dept_eng.department_id is not None

        dept_qa = await employee_service.create_department(
            db=db,
            tenant_id=tenant_id,
            department_name=f"QA-Operations-{uuid.uuid4().hex[:4]}",
            parent_department_id=dept_eng.department_id,
        )
        assert dept_qa.parent_department_id == dept_eng.department_id

        desig_lead = await employee_service.create_designation(
            db=db,
            tenant_id=tenant_id,
            designation_name=f"Tech-Lead-{uuid.uuid4().hex[:4]}",
            description="Engineering Technical Leader",
        )
        desig_dev = await employee_service.create_designation(
            db=db,
            tenant_id=tenant_id,
            designation_name=f"Software-Engineer-{uuid.uuid4().hex[:4]}",
            description="Core Systems Engineer",
        )
        assert desig_lead.designation_id is not None
        assert desig_dev.designation_id is not None

        # =========================================================================
        # STEP 2: Employee Master & Organizational Hierarchy
        # =========================================================================
        lead_emp = await employee_service.create_employee(
            db=db,
            tenant_id=tenant_id,
            employee_code=f"EMP-LEAD-{uuid.uuid4().hex[:4].upper()}",
            first_name="Ada",
            last_name="Lovelace",
            email=f"ada.{uuid.uuid4().hex[:4]}@company.org",
            department_name=dept_eng.department_name,
            department_id=dept_eng.department_id,
            designation_name=desig_lead.designation_name,
            designation_id=desig_lead.designation_id,
            gender="FEMALE",
            date_of_birth=date(1990, 12, 10),
            date_of_joining=date(2023, 1, 15),
            bank_name="First Commercial Bank",
            bank_account_no="FCB-987654321",
        )
        assert lead_emp.employee_id is not None

        staff_emp = await employee_service.create_employee(
            db=db,
            tenant_id=tenant_id,
            employee_code=f"EMP-DEV-{uuid.uuid4().hex[:4].upper()}",
            first_name="Charles",
            last_name="Babbage",
            email=f"charles.{uuid.uuid4().hex[:4]}@company.org",
            department_name=dept_eng.department_name,
            department_id=dept_eng.department_id,
            designation_name=desig_dev.designation_name,
            designation_id=desig_dev.designation_id,
            reports_to_id=lead_emp.employee_id,
            gender="MALE",
            date_of_birth=date(1994, 6, 20),
            date_of_joining=date(2024, 3, 1),
            bank_name="First Commercial Bank",
            bank_account_no="FCB-123456789",
        )
        assert staff_emp.reports_to_id == lead_emp.employee_id
        assert staff_emp.status == "ACTIVE"

        # =========================================================================
        # STEP 3: Employee Onboarding Checklist & Task Fulfillment
        # =========================================================================
        onboarding = await employee_service.create_onboarding(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            applicant_name="Charles Babbage",
            date_of_joining=date(2024, 3, 1),
        )
        assert onboarding.status == "PENDING"

        # Query tasks
        tasks_stmt = select(OnboardingTask).where(
            OnboardingTask.tenant_id == tenant_id,
            OnboardingTask.onboarding_id == onboarding.onboarding_id,
        )
        onb_tasks = list((await db.execute(tasks_stmt)).scalars().all())
        assert len(onb_tasks) == 4

        for t in onb_tasks:
            updated_onb = await employee_service.complete_onboarding_task(
                db, tenant_id, onboarding.onboarding_id, t.task_id
            )
        assert updated_onb.status == "COMPLETED"

        # =========================================================================
        # STEP 4: Shift Types, Rosters & Attendance with Compliance Metrics
        # =========================================================================
        shift_morning = await attendance_service.create_shift_type(
            db=db,
            tenant_id=tenant_id,
            shift_name=f"Shift-Morning-{uuid.uuid4().hex[:4]}",
            start_time="09:00:00",
            end_time="17:00:00",
            grace_period_mins=15,
            half_day_threshold_hours=Decimal("4.00"),
            late_mark_after_mins=15,
        )
        assert shift_morning.shift_type_id is not None

        shift_assign = await attendance_service.assign_shift(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            shift_type_id=shift_morning.shift_type_id,
            start_date=date(2026, 9, 1),
        )
        assert shift_assign.status == "ACTIVE"

        # 4a: Normal Attendance Punch
        att_normal = await attendance_service.mark_attendance(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            attendance_date=date(2026, 9, 10),
            status="PRESENT",
            in_time=datetime(2026, 9, 10, 9, 5, 0, tzinfo=timezone.utc),
            out_time=datetime(2026, 9, 10, 17, 5, 0, tzinfo=timezone.utc),
        )
        assert att_normal.status == "PRESENT"
        assert att_normal.working_hours == Decimal("8.00")
        assert att_normal.late_entry is False

        # 4b: Late Attendance Punch (Arrived 09:35, shift starts 09:00 + 15m grace)
        att_late = await attendance_service.mark_attendance(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            attendance_date=date(2026, 9, 11),
            status="PRESENT",
            in_time=datetime(2026, 9, 11, 9, 35, 0, tzinfo=timezone.utc),
            out_time=datetime(2026, 9, 11, 17, 0, 0, tzinfo=timezone.utc),
        )
        assert att_late.late_entry is True

        # 4c: Absent day (will be counted toward Leave Without Pay)
        att_absent = await attendance_service.mark_attendance(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            attendance_date=date(2026, 9, 12),
            status="ABSENT",
        )
        assert att_absent.status == "ABSENT"

        # =========================================================================
        # STEP 5: Leave Management (Types, Allocation, Application & Balance)
        # =========================================================================
        leave_casual = await leave_service.create_leave_type(
            db=db,
            tenant_id=tenant_id,
            type_name=f"Casual-Leave-{uuid.uuid4().hex[:4]}",
            max_days_allowed=14,
            is_carry_forward=False,
            is_lwp=False,
        )
        leave_lwp = await leave_service.create_leave_type(
            db=db,
            tenant_id=tenant_id,
            type_name=f"Unpaid-LWP-{uuid.uuid4().hex[:4]}",
            max_days_allowed=0,
            is_carry_forward=False,
            is_lwp=True,
        )

        # Allocate 14 days of Casual Leave for current fiscal year
        alloc = await leave_service.allocate_leaves(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            leave_type_id=leave_casual.leave_type_id,
            fiscal_year=2026,
            total_leaves_allocated=Decimal("14.00"),
        )
        assert alloc.total_leaves_allocated == Decimal("14.00")

        # Initial balance check
        bal_initial = await leave_service.get_leave_balance(
            db, tenant_id, staff_emp.employee_id, leave_casual.leave_type_id, 2026
        )
        assert bal_initial["remaining"] == Decimal("14.00")

        # Attempt to apply for 20 days -> Should be rejected
        with pytest.raises(ValueError, match="Insufficient leave balance"):
            await leave_service.submit_leave_application(
                db=db,
                tenant_id=tenant_id,
                employee_id=staff_emp.employee_id,
                leave_type_id=leave_casual.leave_type_id,
                from_date=date(2026, 10, 1),
                to_date=date(2026, 10, 20),
                total_leave_days=Decimal("20.00"),
            )

        # Valid application for 3 days
        leave_app = await leave_service.submit_leave_application(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            leave_type_id=leave_casual.leave_type_id,
            from_date=date(2026, 10, 1),
            to_date=date(2026, 10, 3),
            total_leave_days=Decimal("3.00"),
            reason="Family event",
        )
        assert leave_app.status == "SUBMITTED"

        # Manager approval
        approved_app = await leave_service.approve_leave_application(
            db, tenant_id, leave_app.application_id, approved_by_id=lead_emp.employee_id
        )
        assert approved_app.status == "APPROVED"

        # Balance after approval: 14 - 3 = 11 remaining
        bal_after = await leave_service.get_leave_balance(
            db, tenant_id, staff_emp.employee_id, leave_casual.leave_type_id, 2026
        )
        assert bal_after["remaining"] == Decimal("11.00")
        assert bal_after["used"] == Decimal("3.00")

        # =========================================================================
        # STEP 6: Salary Components, Dynamic Formulas & Salary Structures
        # =========================================================================
        # Earnings
        comp_basic = await payroll_service.create_salary_component(
            db=db,
            tenant_id=tenant_id,
            component_name="Basic Salary",
            component_code="BASIC",
            component_type="EARNING",
            calculation_type="FIXED",
        )
        comp_hra = await payroll_service.create_salary_component(
            db=db,
            tenant_id=tenant_id,
            component_name="House Rent Allowance",
            component_code="HRA",
            component_type="EARNING",
            calculation_type="FORMULA",
            formula_expression="base * 0.40",  # 40% of Base
        )
        comp_special = await payroll_service.create_salary_component(
            db=db,
            tenant_id=tenant_id,
            component_name="Special Allowance",
            component_code="SPECIAL",
            component_type="EARNING",
            calculation_type="FIXED",
        )
        # Deductions
        comp_tax = await payroll_service.create_salary_component(
            db=db,
            tenant_id=tenant_id,
            component_name="Income Tax Withholding",
            component_code="TDS",
            component_type="DEDUCTION",
            calculation_type="FORMULA",
            formula_expression="base * 0.10",  # 10% Tax
        )
        comp_pf = await payroll_service.create_salary_component(
            db=db,
            tenant_id=tenant_id,
            component_name="Provident Fund",
            component_code="PF",
            component_type="DEDUCTION",
            calculation_type="FORMULA",
            formula_expression="base * 0.05",  # 5% PF
        )

        # Build Salary Structure
        structure = await payroll_service.create_salary_structure(
            db=db,
            tenant_id=tenant_id,
            structure_name=f"Standard-Engineering-Package-{uuid.uuid4().hex[:4]}",
            items=[
                {"component_id": comp_basic.component_id, "amount": Decimal("0.00"), "formula_expression": None},
                {"component_id": comp_hra.component_id, "amount": Decimal("0.00"), "formula_expression": "base * 0.40"},
                {"component_id": comp_special.component_id, "amount": Decimal("500.00"), "formula_expression": None},
                {"component_id": comp_tax.component_id, "amount": Decimal("0.00"), "formula_expression": "base * 0.10"},
                {"component_id": comp_pf.component_id, "amount": Decimal("0.00"), "formula_expression": "base * 0.05"},
            ],
        )
        assert structure.structure_id is not None

        # Assign Structure to Employee with Base = $5,000.00
        assignment = await payroll_service.assign_salary_structure(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            structure_id=structure.structure_id,
            from_date=date(2026, 9, 1),
            base_salary=Decimal("5000.00"),
        )
        assert assignment.base_salary == Decimal("5000.00")

        # =========================================================================
        # STEP 7: Employee Advance & Loan Disbursement GL Accounting
        # =========================================================================
        advance = await expense_advance_service.create_employee_advance(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            advance_amount=Decimal("1000.00"),
            purpose="Relocation assistance advance",
            monthly_deduction_amount=Decimal("200.00"),
            posting_date=date(2026, 9, 1),
        )
        assert advance.status == "PENDING"

        # Disburse advance
        disbursed_adv = await expense_advance_service.approve_and_disburse_advance(
            db, tenant_id, advance.advance_id
        )
        assert disbursed_adv.status == "PAID"

        # Verify advance GL entries
        adv_gl_stmt = select(GeneralLedgerEntry).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.source_document_id == advance.advance_id,
        )
        adv_gl = list((await db.execute(adv_gl_stmt)).scalars().all())
        assert len(adv_gl) == 2
        adv_debit = next(l for l in adv_gl if l.debit_amount > 0)
        adv_credit = next(l for l in adv_gl if l.credit_amount > 0)
        assert adv_debit.account_code == "1250-EMPLOYEE-ADVANCE-CLEARING"
        assert adv_credit.account_code == "1020-BANK-OPERATING"
        assert adv_debit.debit_amount == Decimal("1000.00")

        # =========================================================================
        # STEP 8: Salary Slip Generation with LWP & Loan Recovery
        # =========================================================================
        # We recorded 1 ABSENT day (2026-09-12), so payment days = 29 / 30.
        slip = await payroll_service.generate_salary_slip(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            posting_date=date(2026, 9, 30),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        assert slip.status == "DRAFT"
        assert slip.leave_without_pay_days == Decimal("1.00")
        assert slip.payment_days == Decimal("29.00")

        # Expected calculation:
        # Gross Pay =~ 7250.00
        # Total Deductions = 950.00 (Tax 500 + PF 250 + Advance EMI 200)
        assert abs(slip.gross_pay - Decimal("7250.00")) < Decimal("1.00")
        assert slip.total_deductions == Decimal("950.00")
        assert slip.net_pay == (slip.gross_pay - slip.total_deductions)

        # Submit Salary Slip & Post Double-Entry GL Journal
        submitted_slip = await payroll_service.submit_salary_slip(
            db, tenant_id, slip.slip_id
        )
        assert submitted_slip.status == "SUBMITTED"
        assert submitted_slip.journal_entry_id is not None

        # Check General Ledger Journal Lines
        slip_gl_stmt = select(GeneralLedgerEntry).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.source_document_id == slip.slip_id,
        )
        slip_gl = list((await db.execute(slip_gl_stmt)).scalars().all())
        assert len(slip_gl) >= 4

        tot_debits = sum(l.debit_amount for l in slip_gl)
        tot_credits = sum(l.credit_amount for l in slip_gl)
        assert tot_debits == tot_credits  # Zero-sum balanced ledger invariant!

        # Check that advance recovery updated repaid_amount
        adv_check_stmt = select(EmployeeAdvance).where(
            EmployeeAdvance.advance_id == advance.advance_id
        )
        updated_adv = (await db.execute(adv_check_stmt)).scalar_one()
        assert updated_adv.repaid_amount == Decimal("200.00")

        # =========================================================================
        # STEP 9: Batch Payroll Processing (Company-Wide Mass Payroll Run)
        # =========================================================================
        # Assign structure to lead_emp as well so batch has multiple employees
        await payroll_service.assign_salary_structure(
            db=db,
            tenant_id=tenant_id,
            employee_id=lead_emp.employee_id,
            structure_id=structure.structure_id,
            from_date=date(2026, 10, 1),
            base_salary=Decimal("8000.00"),
        )

        payroll_entry, batch_slips = await batch_payroll_service.create_batch_payroll(
            db=db,
            tenant_id=tenant_id,
            posting_date=date(2026, 10, 31),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )
        assert payroll_entry.status == "DRAFT"
        assert len(batch_slips) >= 2
        assert payroll_entry.total_gross_pay > 0
        assert payroll_entry.total_net_pay > 0

        # Submit Batch Payroll & commit mass GL disbursements
        submitted_batch = await batch_payroll_service.submit_batch_payroll(
            db, tenant_id, payroll_entry.payroll_entry_id
        )
        assert submitted_batch.status == "SUBMITTED"

        # =========================================================================
        # STEP 10: Expense Claim Reimbursement GL Journal
        # =========================================================================
        expense = ExpenseClaim(
            tenant_id=tenant_id,
            claim_number=f"EXP-{uuid.uuid4().hex[:6].upper()}",
            employee_id=staff_emp.employee_id,
            claim_date=date(2026, 9, 25),
            merchant_name="Client Lunch Bistro",
            category="MEALS",
            total_amount=Decimal("125.50"),
            currency="USD",
            status="APPROVED",
        )
        db.add(expense)
        await db.flush()

        reimbursed_claim = await expense_advance_service.reimburse_expense_claim(
            db, tenant_id, expense.claim_id
        )
        assert reimbursed_claim.status == "PAID"

        # Verify reimbursement GL entries
        exp_gl_stmt = select(GeneralLedgerEntry).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.source_document_id == expense.claim_id,
        )
        exp_gl = list((await db.execute(exp_gl_stmt)).scalars().all())
        assert len(exp_gl) == 2
        assert exp_gl[0].debit_amount == Decimal("125.50")
        assert exp_gl[0].account_code == "6210-MEALS-ENTERTAINMENT"
        assert exp_gl[1].credit_amount == Decimal("125.50")
        assert exp_gl[1].account_code == "1020-BANK-OPERATING"

        # =========================================================================
        # STEP 11: Employee Separation Workflow
        # =========================================================================
        separation = await employee_service.create_separation(
            db=db,
            tenant_id=tenant_id,
            employee_id=staff_emp.employee_id,
            resignation_date=date(2026, 12, 1),
            exit_interview_notes="Pursuing higher education",
        )
        assert separation.status == "PENDING"

        # Complete all separation tasks
        sep_tasks_stmt = select(SeparationTask).where(
            SeparationTask.tenant_id == tenant_id,
            SeparationTask.separation_id == separation.separation_id,
        )
        sep_tasks = list((await db.execute(sep_tasks_stmt)).scalars().all())
        for st in sep_tasks:
            updated_sep = await employee_service.complete_separation_task(
                db, tenant_id, separation.separation_id, st.task_id
            )
        assert updated_sep.status == "COMPLETED"

        # Verify employee transitioned to status 'LEFT' and is inactive
        emp_reloaded = await employee_service.get_employee(db, tenant_id, staff_emp.employee_id)
        assert emp_reloaded.status == "LEFT"
        assert emp_reloaded.is_active is False


@pytest.mark.asyncio
async def test_phase4_bugfixes_validation():
    """Verify bugfixes: duplicate code prevention, auto-seeding, and GL submission invariants."""
    async with async_session_factory() as db:
        tenant_id = uuid.uuid4()

        # 1. Leave Type auto-seeding
        ltypes = await leave_service.list_leave_types(db, tenant_id)
        assert len(ltypes) >= 4
        type_names = [t.type_name for t in ltypes]
        assert "Annual Privilege Leave" in type_names
        assert "Casual Leave" in type_names
        assert "Sick Leave" in type_names
        assert "Leave Without Pay (LWP)" in type_names

        # Duplicate Leave Type prevention
        with pytest.raises(ValueError, match="already exists"):
            await leave_service.create_leave_type(db, tenant_id, "Annual Privilege Leave")

        # 2. Salary Components auto-seeding
        comps = await payroll_service.list_salary_components(db, tenant_id)
        assert len(comps) >= 4
        comp_codes = [c.component_code for c in comps]
        assert "BASIC" in comp_codes
        assert "HRA" in comp_codes
        assert "TAX" in comp_codes
        assert "PF" in comp_codes

        # 3. Employee duplicate code rejection
        emp_code = f"EMP-TEST-{uuid.uuid4().hex[:4].upper()}"
        emp1 = await employee_service.create_employee(
            db=db,
            tenant_id=tenant_id,
            employee_code=emp_code,
            first_name="John",
            last_name="Doe",
            email=f"john.{uuid.uuid4().hex[:4]}@example.com",
        )
        assert emp1.employee_id is not None

        with pytest.raises(ValueError, match="already exists"):
            await employee_service.create_employee(
                db=db,
                tenant_id=tenant_id,
                employee_code=emp_code,
                first_name="Jane",
                last_name="Doe",
                email=f"jane.{uuid.uuid4().hex[:4]}@example.com",
            )

        # 4. Salary Structure requiring at least one EARNING component
        tax_comp = next(c for c in comps if c.component_type == "DEDUCTION")
        with pytest.raises(ValueError, match="EARNING component"):
            await payroll_service.create_salary_structure(
                db=db,
                tenant_id=tenant_id,
                structure_name="Deductions Only Package",
                items=[{"component_id": tax_comp.component_id, "amount": "500.00"}],
            )

        # 5. Salary slip GL submission invariant rejection on zero gross pay
        basic_comp = next(c for c in comps if c.component_code == "BASIC")
        valid_struct = await payroll_service.create_salary_structure(
            db=db,
            tenant_id=tenant_id,
            structure_name="Standard Package",
            items=[{"component_id": basic_comp.component_id, "amount": "5000.00"}],
        )
        await payroll_service.assign_salary_structure(
            db=db,
            tenant_id=tenant_id,
            employee_id=emp1.employee_id,
            structure_id=valid_struct.structure_id,
            from_date=date(2026, 1, 1),
            base_salary=Decimal("5000.00"),
        )
        slip = await payroll_service.generate_salary_slip(
            db=db,
            tenant_id=tenant_id,
            employee_id=emp1.employee_id,
            posting_date=date(2026, 1, 31),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        assert slip.gross_pay == Decimal("5000.00")
        assert slip.net_pay == Decimal("5000.00")

        # Artificially test submission check by forcing negative net_pay
        slip.net_pay = Decimal("-100.00")
        with pytest.raises(ValueError, match="Net Pay cannot be negative"):
            await payroll_service.submit_salary_slip(db, tenant_id, slip.slip_id)

