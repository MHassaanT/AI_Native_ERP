"""Add customer invoice payment terms.

Revision ID: 008_customer_payment_terms
Revises: 007_dag_execution_records
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_customer_payment_terms"
down_revision: str | None = "007_dag_execution_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "customers" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("customers")}
    if "payment_terms_days" not in columns:
        op.add_column(
            "customers",
            sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        )

    constraints = {constraint["name"] for constraint in inspector.get_check_constraints("customers")}
    if "ck_customer_payment_terms_days" not in constraints:
        op.create_check_constraint(
            "ck_customer_payment_terms_days",
            "customers",
            "payment_terms_days BETWEEN 0 AND 3650",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "customers" not in inspector.get_table_names():
        return
    constraints = {constraint["name"] for constraint in inspector.get_check_constraints("customers")}
    if "ck_customer_payment_terms_days" in constraints:
        op.drop_constraint("ck_customer_payment_terms_days", "customers", type_="check")
    columns = {column["name"] for column in inspector.get_columns("customers")}
    if "payment_terms_days" in columns:
        op.drop_column("customers", "payment_terms_days")
