"""Compensation and Payroll Domain Models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class SalaryComponent(Base, TenantMixin, TimestampMixin):
    """Earning and deduction line item definitions."""

    __tablename__ = "salary_components"

    component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_name: Mapped[str] = mapped_column(String(128), nullable=False)
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    component_type: Mapped[str] = mapped_column(
        String(32), nullable=False  # EARNING, DEDUCTION
    )
    calculation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FIXED"  # FIXED, FORMULA
    )
    formula_expression: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Safe arithmetic formula e.g. 'base * 0.40'"
    )
    is_taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    account_code: Mapped[str] = mapped_column(
        String(64), nullable=False, default="6100-SALARY-EXPENSE"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_sal_comp_code", "tenant_id", "component_code", unique=True),
    )


class SalaryStructure(Base, TenantMixin, TimestampMixin):
    """Salary package definition combining earnings and deductions."""

    __tablename__ = "salary_structures"

    structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    structure_name: Mapped[str] = mapped_column(String(128), nullable=False)
    payroll_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MONTHLY"  # MONTHLY, BI_WEEKLY, WEEKLY
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items = relationship(
        "SalaryStructureItem", back_populates="structure", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sal_struct_name", "tenant_id", "structure_name", unique=True),
    )


class SalaryStructureItem(Base, TenantMixin, TimestampMixin):
    """Component rule within a salary structure."""

    __tablename__ = "salary_structure_items"

    structure_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_structures.structure_id"), nullable=False
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_components.component_id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    formula_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)

    structure = relationship("SalaryStructure", back_populates="items")
    component = relationship("SalaryComponent")


class SalaryStructureAssignment(Base, TenantMixin, TimestampMixin):
    """Assignment of salary structure and base salary to an employee."""

    __tablename__ = "salary_structure_assignments"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_structures.structure_id"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    structure = relationship("SalaryStructure")

    __table_args__ = (
        Index("idx_sal_assign_emp_date", "tenant_id", "employee_id", "from_date"),
    )


class SalarySlip(Base, TenantMixin, TimestampMixin):
    """Periodic employee paystub with calculated earnings, deductions, and GL linkage."""

    __tablename__ = "salary_slips"

    slip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slip_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    total_working_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    payment_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("30.00")
    )
    leave_without_pay_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("0.00")
    )
    gross_pay: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_deductions: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    net_pay: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    income_tax: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    payroll_period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_periods.payroll_period_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, PAID, CANCELLED
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    items = relationship("SalarySlipItem", back_populates="slip", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sal_slip_num", "tenant_id", "slip_number", unique=True),
        Index("idx_sal_slip_emp_period", "tenant_id", "employee_id", "start_date", "end_date"),
        Index(
            "uq_sal_slip_active_employee_period",
            "tenant_id", "employee_id", "start_date", "end_date",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
        ),
    )


class SalarySlipItem(Base, TenantMixin, TimestampMixin):
    """Line item on an individual salary slip."""

    __tablename__ = "salary_slip_items"

    slip_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_slips.slip_id"), nullable=False
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_components.component_id"), nullable=True
    )
    component_name: Mapped[str] = mapped_column(String(128), nullable=False)
    component_type: Mapped[str] = mapped_column(String(32), nullable=False)  # EARNING, DEDUCTION
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    slip = relationship("SalarySlip", back_populates="items")


class PayrollEntry(Base, TenantMixin, TimestampMixin):
    """Batch monthly payroll run processing multiple employee salary slips simultaneously."""

    __tablename__ = "payroll_entries"

    payroll_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payroll_number: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True
    )
    payment_account_code: Mapped[str] = mapped_column(
        String(64), nullable=False, default="2100-PAYROLL-PAYABLE"
    )
    expense_account_code: Mapped[str] = mapped_column(
        String(64), nullable=False, default="6100-SALARY-EXPENSE"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, CANCELLED
    )
    total_gross_pay: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_net_pay: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    __table_args__ = (
        Index("idx_payroll_entry_num", "tenant_id", "payroll_number", unique=True),
    )


class EmployeeAdvance(Base, TenantMixin, TimestampMixin):
    """Employee loan or cash advance with salary slip EMI recovery."""

    __tablename__ = "employee_advances"

    advance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    advance_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    advance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_deduction_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    repaid_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"  # PENDING, APPROVED, PAID, REPAID
    )

    __table_args__ = (
        Index("idx_emp_adv_num", "tenant_id", "advance_number", unique=True),
        Index("idx_emp_adv_emp_status", "tenant_id", "employee_id", "status"),
    )


class IncomeTaxSlab(Base, TenantMixin, TimestampMixin):
    """Tax schedule for an annual tax year and currency; rates are progressive bands."""

    __tablename__ = "income_tax_slabs"
    slab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slab_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tax_year: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rates = relationship("IncomeTaxSlabRate", back_populates="slab", cascade="all, delete-orphan")
    __table_args__ = (Index("uq_income_tax_slab_tenant_year", "tenant_id", "tax_year", unique=True),)


class IncomeTaxSlabRate(Base, TenantMixin, TimestampMixin):
    """One progressive annual income band (upper bound NULL means uncapped)."""

    __tablename__ = "income_tax_slab_rates"
    rate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("income_tax_slabs.slab_id", ondelete="CASCADE"), nullable=False)
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    fixed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    slab = relationship("IncomeTaxSlab", back_populates="rates")
    __table_args__ = (Index("idx_tax_rate_slab_lower", "tenant_id", "slab_id", "lower_bound", unique=True),)


class PayrollPeriod(Base, TenantMixin, TimestampMixin):
    __tablename__ = "payroll_periods"
    payroll_period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    __table_args__ = (Index("uq_payroll_period_tenant_dates", "tenant_id", "start_date", "end_date", unique=True),)


class AdditionalSalary(Base, TenantMixin, TimestampMixin):
    __tablename__ = "additional_salaries"
    additional_salary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    salary_component_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salary_components.component_id"), nullable=True)
    payroll_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    component_name: Mapped[str] = mapped_column(String(128), nullable=False)
    component_type: Mapped[str] = mapped_column(String(24), nullable=False, default="EARNING")
    is_taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    slip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salary_slips.slip_id"), nullable=True)
    __table_args__ = (Index("idx_additional_salary_employee_date", "tenant_id", "employee_id", "payroll_date", "status"),)


class RetentionBonus(Base, TenantMixin, TimestampMixin):
    __tablename__ = "retention_bonuses"
    retention_bonus_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=False)
    bonus_name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    vesting_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    slip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salary_slips.slip_id"), nullable=True)
    __table_args__ = (Index("idx_retention_employee_date", "tenant_id", "employee_id", "vesting_date", "status"),)
