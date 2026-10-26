"""Add explicit party/control-leg attribution and invoice settlement references.

Revision ID: 047_party_ledger_dimensions
Revises: 046_credit_note_sales_invoice_lineage
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "047_party_ledger_dimensions"
down_revision = "046_credit_note_sales_invoice_lineage"
branch_labels = None
depends_on = None


def upgrade():
    # Existing due dates cannot be reconstructed from mutable supplier terms.
    op.add_column("supplier_invoices", sa.Column("due_date", sa.Date(), nullable=True))
    for name, kind in (
        ("party_type", sa.String(16)), ("party_id", postgresql.UUID(as_uuid=True)),
        ("party_name_snapshot", sa.String(255)), ("against_document_type", sa.String(32)),
        ("against_document_id", postgresql.UUID(as_uuid=True)),
    ):
        op.add_column("general_ledger_entries", sa.Column(name, kind, nullable=True))
    op.create_check_constraint("ck_gl_party_complete", "general_ledger_entries",
        "(party_type IS NULL AND party_id IS NULL AND party_name_snapshot IS NULL) OR "
        "(party_type IS NOT NULL AND party_type IN ('CUSTOMER','SUPPLIER') AND party_id IS NOT NULL AND party_name_snapshot IS NOT NULL)")
    op.create_check_constraint("ck_gl_against_complete", "general_ledger_entries",
        "(against_document_type IS NULL AND against_document_id IS NULL) OR "
        "(against_document_type IS NOT NULL AND against_document_type IN ('SALES_INVOICE','SUPPLIER_INVOICE') AND against_document_id IS NOT NULL AND party_id IS NOT NULL)")
    op.create_index("ix_gl_tenant_party_date", "general_ledger_entries", ["tenant_id", "party_type", "party_id", "posting_date", "entry_id"])
    op.create_index("ix_gl_tenant_against", "general_ledger_entries", ["tenant_id", "against_document_type", "against_document_id"])

    # Only documented source IDs and known control accounts are backfilled.
    # Revenue/bank/tax counterpart legs and ambiguous legacy accounts stay null.
    sources = [
        ("SALES_INVOICE", "sales_invoices", "invoice_id", "customer", "invoice_id", "SALES_INVOICE"),
        ("SUBSCRIPTION_INVOICE", "sales_invoices", "invoice_id", "customer", "invoice_id", "SALES_INVOICE"),
        ("AUTO_BANK_RECONCILIATION", "sales_invoices", "invoice_id", "customer", "invoice_id", "SALES_INVOICE"),
        ("CREDIT_NOTE", "credit_notes", "credit_note_id", "customer", "invoice_id", "SALES_INVOICE"),
        ("AUTOMATED_AP_MATCH", "supplier_invoices", "invoice_id", "supplier", "invoice_id", "SUPPLIER_INVOICE"),
        ("SUPPLIER_INVOICE", "supplier_invoices", "invoice_id", "supplier", "invoice_id", "SUPPLIER_INVOICE"),
        ("PURCHASE_INVOICE", "supplier_invoices", "invoice_id", "supplier", "invoice_id", "SUPPLIER_INVOICE"),
        ("DEBIT_NOTE", "debit_notes", "debit_note_id", "supplier", "supplier_invoice_id", "SUPPLIER_INVOICE"),
    ]
    for source, table, pk, party, against_column, against_type in sources:
        accounts = "'1200-AR-CUSTOMERS'" if party == "customer" else "'2100-AP-VENDORS','2000-ACCOUNTS-PAYABLE'"
        op.execute(sa.text(f"""
            UPDATE general_ledger_entries g
            SET party_type = '{party.upper()}', party_id = p.{party}_id,
                party_name_snapshot = p.{party}_name,
                against_document_type = CASE WHEN d.{against_column} IS NOT NULL THEN '{against_type}' END,
                against_document_id = d.{against_column}
            FROM {table} d JOIN {party}s p
              ON p.{party}_id = d.{party}_id AND p.tenant_id = d.tenant_id
            WHERE g.tenant_id = d.tenant_id AND g.source_document_id = d.{pk}
              AND g.source_document_type = '{source}' AND g.account_code IN ({accounts})
              AND g.party_id IS NULL
        """))


def downgrade():
    op.drop_index("ix_gl_tenant_against", table_name="general_ledger_entries")
    op.drop_index("ix_gl_tenant_party_date", table_name="general_ledger_entries")
    op.drop_constraint("ck_gl_against_complete", "general_ledger_entries", type_="check")
    op.drop_constraint("ck_gl_party_complete", "general_ledger_entries", type_="check")
    for name in ("against_document_id", "against_document_type", "party_name_snapshot", "party_id", "party_type"):
        op.drop_column("general_ledger_entries", name)
    op.drop_column("supplier_invoices", "due_date")
