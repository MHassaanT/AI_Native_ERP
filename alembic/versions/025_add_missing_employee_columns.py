"""Add missing columns to employees table.

Revision ID: 025_add_missing_employee_columns
Revises: 024_add_employee_reports_to_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "025_add_missing_employee_columns"
down_revision: str = "024_add_employee_reports_to_id"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('employees')]
    
    # Add gender column
    if 'gender' not in columns:
        op.add_column('employees', sa.Column('gender', sa.String(32), nullable=True))
    
    # Add date_of_birth column
    if 'date_of_birth' not in columns:
        op.add_column('employees', sa.Column('date_of_birth', sa.Date(), nullable=True))
    
    # Add date_of_joining column
    if 'date_of_joining' not in columns:
        op.add_column('employees', sa.Column('date_of_joining', sa.Date(), nullable=True))
    
    # Add employment_type column
    if 'employment_type' not in columns:
        op.add_column(
            'employees',
            sa.Column('employment_type', sa.String(32), nullable=False, server_default='FULL_TIME')
        )
    
    # Add status column
    if 'status' not in columns:
        op.add_column(
            'employees',
            sa.Column('status', sa.String(32), nullable=False, server_default='ACTIVE')
        )
    
    # Add phone column
    if 'phone' not in columns:
        op.add_column('employees', sa.Column('phone', sa.String(64), nullable=True))
    
    # Add emergency_phone column
    if 'emergency_phone' not in columns:
        op.add_column('employees', sa.Column('emergency_phone', sa.String(64), nullable=True))
    
    # Add bank_name column
    if 'bank_name' not in columns:
        op.add_column('employees', sa.Column('bank_name', sa.String(128), nullable=True))
    
    # Add bank_account_no column
    if 'bank_account_no' not in columns:
        op.add_column('employees', sa.Column('bank_account_no', sa.String(64), nullable=True))
    
    # Add iban_or_routing column
    if 'iban_or_routing' not in columns:
        op.add_column('employees', sa.Column('iban_or_routing', sa.String(64), nullable=True))
    
    # Add certifications column (array of strings)
    if 'certifications' not in columns:
        op.add_column(
            'employees',
            sa.Column('certifications', postgresql.ARRAY(sa.String(64)), nullable=False, server_default='{}')
        )
    
    # Add max_weekly_hours column
    if 'max_weekly_hours' not in columns:
        op.add_column('employees', sa.Column('max_weekly_hours', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop columns in reverse order
    op.drop_column('employees', 'max_weekly_hours')
    op.drop_column('employees', 'certifications')
    op.drop_column('employees', 'iban_or_routing')
    op.drop_column('employees', 'bank_account_no')
    op.drop_column('employees', 'bank_name')
    op.drop_column('employees', 'emergency_phone')
    op.drop_column('employees', 'phone')
    op.drop_column('employees', 'status')
    op.drop_column('employees', 'employment_type')
    op.drop_column('employees', 'date_of_joining')
    op.drop_column('employees', 'date_of_birth')
    op.drop_column('employees', 'gender')
