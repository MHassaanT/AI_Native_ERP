"""Persist salary slip currency and prevent duplicate active payroll periods.

Revision ID: 038_payroll_currency_and_period_guard
Revises: 037_enterprise_report_indexes
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "038_payroll_currency_and_period_guard"
down_revision: str | None = "037_enterprise_report_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("salary_slips", sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"))
    op.execute(sa.text("""
        UPDATE salary_slips AS slip
        SET currency = COALESCE(
            (SELECT structure.currency
             FROM salary_structure_assignments AS assignment
             JOIN salary_structures AS structure
               ON structure.structure_id = assignment.structure_id
              AND structure.tenant_id = assignment.tenant_id
             WHERE assignment.tenant_id = slip.tenant_id
               AND assignment.employee_id = slip.employee_id
               AND assignment.from_date <= slip.posting_date
             ORDER BY assignment.from_date DESC
             LIMIT 1),
            (SELECT tenant.currency FROM tenants AS tenant WHERE tenant.tenant_id = slip.tenant_id),
            'USD'
        )
    """))
    op.create_index(
        "uq_sal_slip_active_employee_period",
        "salary_slips",
        ["tenant_id", "employee_id", "start_date", "end_date"],
        unique=True,
        postgresql_where=sa.text("status <> 'CANCELLED'"),
    )


def downgrade() -> None:
    op.drop_index("uq_sal_slip_active_employee_period", table_name="salary_slips")
    op.drop_column("salary_slips", "currency")
