"""Add department_id and designation_id foreign keys to employees table.

Revision ID: 021_add_employee_department_id
Revises: 020_autonomous_hr_and_pacing
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "021_add_employee_department_id"
down_revision: str | None = "020_autonomous_hr_and_pacing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add department_id foreign key column to employees table
    op.add_column(
        "employees",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_employees_department_id",
        "employees",
        "departments",
        ["department_id"],
        ["department_id"],
    )
    op.create_index("ix_employees_department_id", "employees", ["department_id"])

    # Add designation_id foreign key column to employees table (if not already present)
    # Check if column exists first to avoid errors
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('employees')]
    
    if 'designation_id' not in columns:
        op.add_column(
            "employees",
            sa.Column(
                "designation_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_employees_designation_id",
            "employees",
            "designations",
            ["designation_id"],
            ["designation_id"],
        )
        op.create_index("ix_employees_designation_id", "employees", ["designation_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('employees')]
    
    if 'designation_id' in columns:
        op.drop_index("ix_employees_designation_id", table_name="employees")
        op.drop_constraint("fk_employees_designation_id", "employees", type_="foreignkey")
        op.drop_column("employees", "designation_id")
    
    op.drop_index("ix_employees_department_id", table_name="employees")
    op.drop_constraint("fk_employees_department_id", "employees", type_="foreignkey")
    op.drop_column("employees", "department_id")
