"""002 Multi-tenant Auth and Operator Certifications Schema

Revision ID: 002_multi_tenant_auth_and_certs
Revises: 001_initial_schema
Create Date: 2026-09-19 18:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_multi_tenant_auth_and_certs"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Tenants Table
    if "tenants" not in existing_tables:
        op.create_table(
            "tenants",
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_slug", sa.String(length=64), nullable=False),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
            sa.Column("plan_tier", sa.String(length=32), server_default="ENTERPRISE", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index("idx_tenant_slug", "tenants", ["tenant_slug"], unique=True)

    # 2. Users Table
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=32), server_default="TENANT_ADMIN", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index("idx_user_tenant_email", "users", ["tenant_id", "email"], unique=True)
        op.create_index("idx_users_tenant_id", "users", ["tenant_id"])
        op.create_index("idx_users_email", "users", ["email"])

    # 3. Operator Certifications Table
    if "operator_certifications" not in existing_tables:
        op.create_table(
            "operator_certifications",
            sa.Column(
                "cert_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "employee_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("employees.employee_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("employee_code", sa.String(length=64), nullable=False),
            sa.Column("certification_code", sa.String(length=64), nullable=False),
            sa.Column("certification_name", sa.String(length=128), nullable=False),
            sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("expiry_date", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_cert_tenant_emp_code",
            "operator_certifications",
            ["tenant_id", "employee_code", "certification_code"],
            unique=True,
        )
        op.create_index("idx_operator_certifications_tenant_id", "operator_certifications", ["tenant_id"])
        op.create_index("idx_operator_certifications_employee_code", "operator_certifications", ["employee_code"])
        op.create_index("idx_operator_certifications_certification_code", "operator_certifications", ["certification_code"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "operator_certifications" in existing_tables:
        op.drop_table("operator_certifications")
    if "users" in existing_tables:
        op.drop_table("users")
    if "tenants" in existing_tables:
        op.drop_table("tenants")
