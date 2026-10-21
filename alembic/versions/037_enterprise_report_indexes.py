"""Add tenant and date indexes used by Phase F report queries.

Revision ID: 037_enterprise_report_indexes
Revises: 036_projects_support_refinements
"""
from collections.abc import Sequence

from alembic import op

revision: str = "037_enterprise_report_indexes"
down_revision: str | None = "036_projects_support_refinements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


INDEXES = (
    ("ix_report_sales_invoice_tenant_date", "sales_invoices", ["tenant_id", "invoice_date"]),
    ("ix_report_supplier_invoice_tenant_date", "supplier_invoices", ["tenant_id", "invoice_date"]),
    ("ix_report_sales_order_tenant_date", "sales_orders", ["tenant_id", "order_date"]),
    ("ix_report_sales_quote_tenant_date", "sales_quotations", ["tenant_id", "quotation_date"]),
    ("ix_report_delivery_note_tenant_date", "delivery_notes", ["tenant_id", "delivery_date"]),
    ("ix_report_issue_tenant_assignee_status", "issues", ["tenant_id", "assigned_to_id", "status"]),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
