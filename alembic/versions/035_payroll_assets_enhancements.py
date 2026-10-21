"""Add tax, payroll period and additions workflows plus asset team/revaluation.

Revision ID: 035_payroll_assets_enhancements
Revises: 034_hr_deep_workflows
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "035_payroll_assets_enhancements"
down_revision: str | None = "034_hr_deep_workflows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None
U = postgresql.UUID(as_uuid=True)


def common():
    return [sa.Column("tenant_id", U, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False)]


def table(name, pk, *columns, constraints=()):
    op.create_table(name, sa.Column(pk, U, primary_key=True, nullable=False), *common(), *columns, *constraints)


def upgrade() -> None:
    table("income_tax_slabs", "slab_id", sa.Column("slab_name", sa.String(128), nullable=False),
          sa.Column("tax_year", sa.String(16), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
          sa.Column("effective_from", sa.Date(), nullable=False), sa.Column("effective_to", sa.Date(), nullable=False),
          sa.Column("is_active", sa.Boolean(), nullable=False), constraints=(
              sa.UniqueConstraint("tenant_id", "tax_year", name="uq_income_tax_slab_tenant_year"),
              sa.CheckConstraint("effective_to >= effective_from", name="ck_income_tax_slab_dates")))
    table("income_tax_slab_rates", "rate_id", sa.Column("slab_id", U, sa.ForeignKey("income_tax_slabs.slab_id", ondelete="CASCADE"), nullable=False),
          sa.Column("lower_bound", sa.Numeric(18, 4), nullable=False), sa.Column("upper_bound", sa.Numeric(18, 4)),
          sa.Column("tax_rate", sa.Numeric(8, 6), nullable=False), sa.Column("fixed_amount", sa.Numeric(18, 4), nullable=False),
          constraints=(sa.CheckConstraint("lower_bound >= 0 AND (upper_bound IS NULL OR upper_bound > lower_bound)", name="ck_tax_slab_rate_bounds"),
                       sa.CheckConstraint("tax_rate >= 0 AND tax_rate <= 1 AND fixed_amount >= 0", name="ck_tax_slab_rate_values")))
    table("payroll_periods", "payroll_period_id", sa.Column("period_name", sa.String(128), nullable=False),
          sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False),
          sa.Column("status", sa.String(24), nullable=False), constraints=(
              sa.UniqueConstraint("tenant_id", "start_date", "end_date", name="uq_payroll_period_tenant_dates"),
              sa.CheckConstraint("end_date >= start_date", name="ck_payroll_period_dates"),
              sa.CheckConstraint("status IN ('OPEN','CLOSED')", name="ck_payroll_period_status")))
    op.add_column("salary_slips", sa.Column("income_tax", sa.Numeric(18, 4), server_default="0", nullable=False))
    op.add_column("salary_slips", sa.Column("payroll_period_id", U, nullable=True))
    op.create_foreign_key("fk_salary_slip_payroll_period", "salary_slips", "payroll_periods", ["payroll_period_id"], ["payroll_period_id"], ondelete="SET NULL")
    table("additional_salaries", "additional_salary_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False),
          sa.Column("salary_component_id", U, sa.ForeignKey("salary_components.component_id")), sa.Column("payroll_date", sa.Date(), nullable=False),
          sa.Column("amount", sa.Numeric(18, 4), nullable=False), sa.Column("component_name", sa.String(128), nullable=False),
          sa.Column("component_type", sa.String(24), nullable=False), sa.Column("is_taxable", sa.Boolean(), nullable=False),
          sa.Column("status", sa.String(24), nullable=False), sa.Column("slip_id", U, sa.ForeignKey("salary_slips.slip_id", ondelete="SET NULL")),
          constraints=(sa.CheckConstraint("amount > 0", name="ck_additional_salary_amount"),
                       sa.CheckConstraint("component_type IN ('EARNING','DEDUCTION')", name="ck_additional_salary_type"),
                       sa.CheckConstraint("status IN ('PENDING','INCLUDED','PAID','CANCELLED')", name="ck_additional_salary_status")))
    table("retention_bonuses", "retention_bonus_id", sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False),
          sa.Column("bonus_name", sa.String(128), nullable=False), sa.Column("amount", sa.Numeric(18, 4), nullable=False),
          sa.Column("vesting_date", sa.Date(), nullable=False), sa.Column("is_taxable", sa.Boolean(), nullable=False),
          sa.Column("status", sa.String(24), nullable=False), sa.Column("slip_id", U, sa.ForeignKey("salary_slips.slip_id", ondelete="SET NULL")),
          constraints=(sa.CheckConstraint("amount > 0", name="ck_retention_bonus_amount"),
                       sa.CheckConstraint("status IN ('PENDING','EARNED','PAID','CANCELLED')", name="ck_retention_bonus_status")))
    table("asset_maintenance_teams", "team_id", sa.Column("team_name", sa.String(128), nullable=False),
          sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False),
          constraints=(sa.UniqueConstraint("tenant_id", "team_name", name="uq_asset_maintenance_team_tenant_name"),))
    table("asset_maintenance_team_members", "member_id", sa.Column("team_id", U, sa.ForeignKey("asset_maintenance_teams.team_id", ondelete="CASCADE"), nullable=False),
          sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id"), nullable=False), sa.Column("role", sa.String(64)),
          constraints=(sa.UniqueConstraint("tenant_id", "team_id", "employee_id", name="uq_asset_maintenance_team_member"),))
    table("asset_value_adjustments", "adjustment_id", sa.Column("asset_id", U, sa.ForeignKey("assets.asset_id"), nullable=False),
          sa.Column("adjustment_date", sa.Date(), nullable=False), sa.Column("previous_book_value", sa.Numeric(18, 4), nullable=False),
          sa.Column("new_book_value", sa.Numeric(18, 4), nullable=False), sa.Column("adjustment_amount", sa.Numeric(18, 4), nullable=False),
          sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("journal_entry_id", U),
          constraints=(sa.CheckConstraint("previous_book_value >= 0 AND new_book_value >= 0 AND adjustment_amount <> 0", name="ck_asset_value_adjustment_values"),
                       sa.CheckConstraint("status IN ('DRAFT','POSTED','CANCELLED')", name="ck_asset_value_adjustment_status")))
    for name in ("income_tax_slabs", "income_tax_slab_rates", "payroll_periods", "additional_salaries", "retention_bonuses", "asset_maintenance_teams", "asset_maintenance_team_members", "asset_value_adjustments"):
        op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
    op.create_index("ix_tax_rate_slab_lower", "income_tax_slab_rates", ["tenant_id", "slab_id", "lower_bound"], unique=True)
    op.create_index("idx_additional_salary_employee_date", "additional_salaries", ["tenant_id", "employee_id", "payroll_date", "status"])
    op.create_index("idx_retention_employee_date", "retention_bonuses", ["tenant_id", "employee_id", "vesting_date", "status"])
    op.create_index("idx_asset_value_adjustment", "asset_value_adjustments", ["tenant_id", "asset_id", "adjustment_date"])


def downgrade() -> None:
    for index, table_name in (("idx_asset_value_adjustment", "asset_value_adjustments"), ("idx_retention_employee_date", "retention_bonuses"), ("idx_additional_salary_employee_date", "additional_salaries"), ("ix_tax_rate_slab_lower", "income_tax_slab_rates")):
        op.drop_index(index, table_name=table_name)
    op.drop_constraint("fk_salary_slip_payroll_period", "salary_slips", type_="foreignkey")
    op.drop_column("salary_slips", "payroll_period_id")
    op.drop_column("salary_slips", "income_tax")
    for name in ("asset_value_adjustments", "asset_maintenance_team_members", "asset_maintenance_teams", "retention_bonuses", "additional_salaries", "payroll_periods", "income_tax_slab_rates", "income_tax_slabs"):
        op.drop_table(name)
