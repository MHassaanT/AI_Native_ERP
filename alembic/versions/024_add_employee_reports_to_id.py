"""Add reports_to_id column to employees table.

Revision ID: 024_add_employee_reports_to_id
Revises: 023_drop_old_designation_column
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "024_add_employee_reports_to_id"
down_revision: str = "023_drop_old_designation_column"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Add reports_to_id column if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('employees')]
    
    if 'reports_to_id' not in columns:
        op.add_column(
            'employees',
            sa.Column(
                'reports_to_id',
                postgresql.UUID(as_uuid=True),
                nullable=True
            )
        )
        # Add foreign key constraint
        op.create_foreign_key(
            'fk_employees_reports_to_id',
            'employees',
            'employees',
            ['reports_to_id'],
            ['employee_id']
        )
        # Add index for better query performance
        op.create_index(
            'ix_employees_reports_to_id',
            'employees',
            ['reports_to_id']
        )


def downgrade() -> None:
    # Drop the index, foreign key, and column
    op.drop_index('ix_employees_reports_to_id', table_name='employees')
    op.drop_constraint('fk_employees_reports_to_id', 'employees', type_='foreignkey')
    op.drop_column('employees', 'reports_to_id')
