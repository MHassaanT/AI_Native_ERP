"""Add project types, activity costing, and project update linkage.

Revision ID: 036_projects_support_refinements
Revises: 035_payroll_assets_enhancements
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036_projects_support_refinements"
down_revision: str | None = "035_payroll_assets_enhancements"
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
    table("project_types", "project_type_id", sa.Column("type_name", sa.String(128), nullable=False),
          sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False),
          constraints=(sa.UniqueConstraint("tenant_id", "type_name", name="uq_project_type_tenant_name"),))
    table("activity_types", "activity_type_id", sa.Column("activity_name", sa.String(128), nullable=False),
          sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False),
          constraints=(sa.UniqueConstraint("tenant_id", "activity_name", name="uq_activity_type_tenant_name"),))
    table("activity_costs", "activity_cost_id", sa.Column("activity_type_id", U, sa.ForeignKey("activity_types.activity_type_id", ondelete="CASCADE"), nullable=False),
          sa.Column("employee_id", U, sa.ForeignKey("employees.employee_id")), sa.Column("billing_rate", sa.Numeric(18, 4), nullable=False),
          sa.Column("costing_rate", sa.Numeric(18, 4), nullable=False), sa.Column("valid_from", sa.Date(), nullable=False),
          sa.Column("valid_to", sa.Date()), constraints=(sa.CheckConstraint("billing_rate >= 0 AND costing_rate >= 0", name="ck_activity_cost_rates"),
              sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_activity_cost_dates")))
    op.add_column("projects", sa.Column("project_type_id", U, nullable=True))
    op.create_foreign_key("fk_project_type", "projects", "project_types", ["project_type_id"], ["project_type_id"], ondelete="SET NULL")
    op.add_column("timesheets", sa.Column("activity_type_id", U, nullable=True))
    op.create_foreign_key("fk_timesheet_activity_type", "timesheets", "activity_types", ["activity_type_id"], ["activity_type_id"], ondelete="SET NULL")
    for name in ("project_types", "activity_types", "activity_costs"):
        op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
    op.create_index("idx_activity_cost_tenant_type_employee", "activity_costs", ["tenant_id", "activity_type_id", "employee_id", "valid_from"])
    op.create_index("ix_projects_project_type_id", "projects", ["project_type_id"])
    op.create_index("ix_timesheets_activity_type_id", "timesheets", ["activity_type_id"])


def downgrade() -> None:
    op.drop_index("ix_timesheets_activity_type_id", table_name="timesheets")
    op.drop_constraint("fk_timesheet_activity_type", "timesheets", type_="foreignkey")
    op.drop_column("timesheets", "activity_type_id")
    op.drop_index("ix_projects_project_type_id", table_name="projects")
    op.drop_constraint("fk_project_type", "projects", type_="foreignkey")
    op.drop_column("projects", "project_type_id")
    op.drop_index("idx_activity_cost_tenant_type_employee", table_name="activity_costs")
    for name in ("activity_costs", "activity_types", "project_types"):
        op.drop_table(name)
