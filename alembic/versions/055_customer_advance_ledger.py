"""Add customer advance liability account and correct debit-note AP control.

Revision ID: 055_customer_advance_ledger
Revises: 054_pos_profile_price_list
"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "055_customer_advance_ledger"
down_revision: str | None = "054_pos_profile_price_list"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("advance_payment_allocations", sa.Column(
        "ledger_posted", sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    tenant_accounts = bind.execute(sa.text(
        "SELECT tenant_id, currency FROM chart_of_accounts "
        "WHERE account_code = '1200-AR-CUSTOMERS'"
    )).all()
    for tenant_id, currency in tenant_accounts:
        bind.execute(sa.text("""
            INSERT INTO chart_of_accounts
                (account_id, tenant_id, account_code, account_name, account_type,
                 currency, parent_account_code, is_active, created_at, updated_at)
            VALUES
                (:account_id, :tenant_id, '2150-CUSTOMER-ADVANCES',
                 'Customer Advances and Deposits', 'LIABILITY', :currency,
                 NULL, TRUE, clock_timestamp(), clock_timestamp())
            ON CONFLICT (tenant_id, account_code) DO NOTHING
        """), {"account_id": uuid.uuid4(), "tenant_id": tenant_id, "currency": currency})

    # The prior debit-note implementation used a non-standard control code.
    # Its source and party are explicit, so historical rows can be safely
    # reclassified into the supplier AP account used by invoices.
    op.execute(sa.text("""
        UPDATE general_ledger_entries
        SET account_code = '2100-AP-VENDORS'
        WHERE source_document_type = 'DEBIT_NOTE'
          AND account_code = '2000-ACCOUNTS-PAYABLE'
    """))


def downgrade() -> None:
    # Preserve the corrected historical AP classification and customer
    # advance account rows; both may carry financial history.
    op.drop_column("advance_payment_allocations", "ledger_posted")
