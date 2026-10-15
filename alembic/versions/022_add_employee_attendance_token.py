"""Add attendance_token to employees table.

Revision ID: 022_add_employee_attendance_token
Revises: 021_add_employee_department_id
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_add_employee_attendance_token"
down_revision: str | None = "021_add_employee_department_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "attendance_token",
            sa.String(255),
            nullable=True,
            unique=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("employees", "attendance_token")
