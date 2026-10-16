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
    # Expand alembic_version.version_num column to accommodate longer revision IDs
    # This revision ID is 33 characters, exceeding the default VARCHAR(32) limit
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")

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
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)")
