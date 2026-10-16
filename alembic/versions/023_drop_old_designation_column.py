"""Drop the old designation column from employees table.

Revision ID: 023_drop_old_designation_column
Revises: 022_add_employee_attendance_token
"""

from alembic import op
import sqlalchemy as sa


revision: str = "023_drop_old_designation_column"
down_revision: str = "022_add_employee_attendance_token"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Drop the old designation column if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('employees')]
    
    if 'designation' in columns:
        op.drop_column('employees', 'designation')


def downgrade() -> None:
    # Restore the old designation column
    op.add_column(
        'employees',
        sa.Column('designation', sa.String(128), nullable=True)
    )
