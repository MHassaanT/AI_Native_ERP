"""Employee Lifecycle, Departments, Designations, Onboarding and Separation Service."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.hr import (
    Department,
    Designation,
    Employee,
    EmployeeOnboarding,
    EmployeeSeparation,
    OnboardingTask,
    SeparationTask,
)


class EmployeeService:
    """Manages the full employee lifecycle, organization structure, and onboarding/exit tasks."""

    async def create_department(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        department_name: str,
        parent_department_id: uuid.UUID | None = None,
        department_head_id: uuid.UUID | None = None,
    ) -> Department:
        dept = Department(
            tenant_id=tenant_id,
            department_name=department_name,
            parent_department_id=parent_department_id,
            department_head_id=department_head_id,
            is_active=True,
        )
        db.add(dept)
        await db.flush()
        return dept

    async def list_departments(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[Department]:
        stmt = (
            select(Department)
            .where(Department.tenant_id == tenant_id)
            .order_by(Department.department_name.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create_designation(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        designation_name: str,
        description: str | None = None,
    ) -> Designation:
        desig = Designation(
            tenant_id=tenant_id,
            designation_name=designation_name,
            description=description,
            is_active=True,
        )
        db.add(desig)
        await db.flush()
        return desig

    async def list_designations(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[Designation]:
        stmt = (
            select(Designation)
            .where(Designation.tenant_id == tenant_id)
            .order_by(Designation.designation_name.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create_employee(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_code: str,
        first_name: str,
        last_name: str,
        email: str,
        department_name: str = "GENERAL",
        department_id: uuid.UUID | None = None,
        designation_name: str | None = None,
        designation_id: uuid.UUID | None = None,
        reports_to_id: uuid.UUID | None = None,
        gender: str | None = None,
        date_of_birth: date | None = None,
        date_of_joining: date | None = None,
        employment_type: str = "FULL_TIME",
        phone: str | None = None,
        emergency_phone: str | None = None,
        bank_name: str | None = None,
        bank_account_no: str | None = None,
        iban_or_routing: str | None = None,
        certifications: list[str] | None = None,
        max_weekly_hours: int = 48,
    ) -> Employee:
        code_clean = employee_code.strip()
        existing_stmt = select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.employee_code == code_clean,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Employee code '{code_clean}' already exists ({existing.first_name} {existing.last_name}). "
                "Please choose a unique Employee Code."
            )

        emp = Employee(
            tenant_id=tenant_id,
            employee_code=code_clean,
            first_name=first_name,
            last_name=last_name,
            email=email,
            department=department_name,
            department_id=department_id,
            designation=designation_name,
            designation_id=designation_id,
            reports_to_id=reports_to_id,
            gender=gender,
            date_of_birth=date_of_birth,
            date_of_joining=date_of_joining or date.today(),
            employment_type=employment_type,
            status="ACTIVE",
            phone=phone,
            emergency_phone=emergency_phone,
            bank_name=bank_name,
            bank_account_no=bank_account_no,
            iban_or_routing=iban_or_routing,
            certifications=certifications or [],
            max_weekly_hours=max_weekly_hours,
            is_active=True,
        )
        db.add(emp)
        await db.flush()
        return emp

    async def get_employee(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.employee_id == employee_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def list_employees(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Employee]:
        stmt = select(Employee).where(Employee.tenant_id == tenant_id)
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        if status:
            stmt = stmt.where(Employee.status == status)
        stmt = stmt.order_by(Employee.employee_code.asc())
        return list((await db.execute(stmt)).scalars().all())

    async def create_onboarding(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        applicant_name: str | None = None,
        date_of_joining: date | None = None,
        task_names: list[str] | None = None,
    ) -> EmployeeOnboarding:
        onb_number = f"ONB-{date.today().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        onboarding = EmployeeOnboarding(
            tenant_id=tenant_id,
            onboarding_number=onb_number,
            employee_id=employee_id,
            job_applicant_name=applicant_name,
            date_of_joining=date_of_joining or date.today(),
            status="PENDING",
        )
        db.add(onboarding)
        await db.flush()

        default_tasks = task_names or [
            "Collect Identity & Tax Verification Documents",
            "Provision Corporate Email and Workspace Accounts",
            "Hardware & Laptop Handover",
            "Health & Safety Compliance Orientation",
        ]
        for task_name in default_tasks:
            task = OnboardingTask(
                tenant_id=tenant_id,
                onboarding_id=onboarding.onboarding_id,
                task_name=task_name,
                is_completed=False,
            )
            db.add(task)
        await db.flush()
        return onboarding

    async def complete_onboarding_task(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        onboarding_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> EmployeeOnboarding:
        stmt = select(OnboardingTask).where(
            OnboardingTask.tenant_id == tenant_id,
            OnboardingTask.onboarding_id == onboarding_id,
            OnboardingTask.task_id == task_id,
        )
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise ValueError(f"Onboarding task {task_id} not found.")

        task.is_completed = True
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()

        # Check if all tasks are complete
        all_tasks_stmt = select(OnboardingTask).where(
            OnboardingTask.tenant_id == tenant_id,
            OnboardingTask.onboarding_id == onboarding_id,
        )
        all_tasks = list((await db.execute(all_tasks_stmt)).scalars().all())
        all_done = all(t.is_completed for t in all_tasks)

        onb_stmt = select(EmployeeOnboarding).where(
            EmployeeOnboarding.tenant_id == tenant_id,
            EmployeeOnboarding.onboarding_id == onboarding_id,
        )
        onb = (await db.execute(onb_stmt)).scalar_one_or_none()
        if onb:
            onb.status = "COMPLETED" if all_done else "IN_PROGRESS"
            await db.flush()
        return onb

    async def create_separation(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        resignation_date: date,
        exit_interview_notes: str | None = None,
        task_names: list[str] | None = None,
    ) -> EmployeeSeparation:
        sep_number = f"SEP-{date.today().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        separation = EmployeeSeparation(
            tenant_id=tenant_id,
            separation_number=sep_number,
            employee_id=employee_id,
            resignation_date=resignation_date,
            exit_interview_notes=exit_interview_notes,
            status="PENDING",
        )
        db.add(separation)
        await db.flush()

        default_tasks = task_names or [
            "Conduct Exit Interview",
            "Collect Corporate Laptop and Security Badges",
            "Revoke Cloud & Network Credentials",
            "Process Full and Final (F&F) Settlement Calculation",
        ]
        for t_name in default_tasks:
            task = SeparationTask(
                tenant_id=tenant_id,
                separation_id=separation.separation_id,
                task_name=t_name,
                is_completed=False,
            )
            db.add(task)
        await db.flush()
        return separation

    async def complete_separation_task(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        separation_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> EmployeeSeparation:
        stmt = select(SeparationTask).where(
            SeparationTask.tenant_id == tenant_id,
            SeparationTask.separation_id == separation_id,
            SeparationTask.task_id == task_id,
        )
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise ValueError(f"Separation task {task_id} not found.")

        task.is_completed = True
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()

        all_tasks_stmt = select(SeparationTask).where(
            SeparationTask.tenant_id == tenant_id,
            SeparationTask.separation_id == separation_id,
        )
        all_tasks = list((await db.execute(all_tasks_stmt)).scalars().all())
        all_done = all(t.is_completed for t in all_tasks)

        sep_stmt = select(EmployeeSeparation).where(
            EmployeeSeparation.tenant_id == tenant_id,
            EmployeeSeparation.separation_id == separation_id,
        )
        sep = (await db.execute(sep_stmt)).scalar_one_or_none()
        if sep:
            sep.status = "COMPLETED" if all_done else "IN_PROGRESS"
            if all_done:
                # Update employee status to LEFT
                emp = await self.get_employee(db, tenant_id, sep.employee_id)
                if emp:
                    emp.status = "LEFT"
                    emp.is_active = False
            await db.flush()
        return sep

    async def list_onboardings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
    ) -> list[EmployeeOnboarding]:
        stmt = (
            select(EmployeeOnboarding)
            .options(selectinload(EmployeeOnboarding.tasks))
            .where(EmployeeOnboarding.tenant_id == tenant_id)
        )
        if employee_id:
            stmt = stmt.where(EmployeeOnboarding.employee_id == employee_id)
        stmt = stmt.order_by(EmployeeOnboarding.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    async def list_separations(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
    ) -> list[EmployeeSeparation]:
        stmt = (
            select(EmployeeSeparation)
            .options(selectinload(EmployeeSeparation.tasks))
            .where(EmployeeSeparation.tenant_id == tenant_id)
        )
        if employee_id:
            stmt = stmt.where(EmployeeSeparation.employee_id == employee_id)
        stmt = stmt.order_by(EmployeeSeparation.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())


employee_service = EmployeeService()
