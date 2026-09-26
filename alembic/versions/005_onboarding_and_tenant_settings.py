"""005 Onboarding, Tenant Settings, and Multi-Step Setup Schema

Revision ID: 005_onboarding_and_tenant_settings
Revises: 004_tenant_oauth_connections
Create Date: 2026-09-26 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005_onboarding_and_setup"
down_revision: str | None = "004_tenant_oauth_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update tenants table with onboarding and localization columns
    tenant_columns = {c["name"] for c in inspector.get_columns("tenants")}
    if "country" not in tenant_columns:
        op.add_column("tenants", sa.Column("country", sa.String(64), nullable=True))
    if "industry" not in tenant_columns:
        op.add_column("tenants", sa.Column("industry", sa.String(64), nullable=True))
    if "timezone" not in tenant_columns:
        op.add_column("tenants", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"))
    if "fiscal_year_start" not in tenant_columns:
        op.add_column("tenants", sa.Column("fiscal_year_start", sa.Date(), nullable=True))
    if "fiscal_year_end" not in tenant_columns:
        op.add_column("tenants", sa.Column("fiscal_year_end", sa.Date(), nullable=True))
    if "company_size" not in tenant_columns:
        op.add_column("tenants", sa.Column("company_size", sa.String(32), nullable=True))
    if "setup_completed_at" not in tenant_columns:
        op.add_column("tenants", sa.Column("setup_completed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    if "enabled_modules" not in tenant_columns:
        op.add_column("tenants", sa.Column("enabled_modules", postgresql.JSONB(), nullable=False, server_default="[]"))

    # For pre-existing tenants (like default tenant 00000000-0000-0000-0000-000000000001), mark setup as completed
    op.execute("UPDATE tenants SET setup_completed_at = now() WHERE setup_completed_at IS NULL AND created_at < now()")

    # 2. Table: tenant_settings
    if "tenant_settings" not in existing_tables:
        op.create_table(
            "tenant_settings",
            sa.Column("setting_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("valuation_method", sa.String(32), nullable=False, server_default="FIFO"),
            sa.Column(
                "default_warehouse_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("warehouses.warehouse_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("default_buying_price_list", sa.String(128), nullable=True, server_default="Standard Buying"),
            sa.Column("default_selling_price_list", sa.String(128), nullable=True, server_default="Standard Selling"),
            sa.Column("stock_uom", sa.String(32), nullable=False, server_default="Nos"),
            sa.Column("date_format", sa.String(32), nullable=False, server_default="YYYY-MM-DD"),
            sa.Column("number_format", sa.String(32), nullable=False, server_default="#,###.##"),
            sa.Column("margin_floor_pct", sa.Numeric(5, 2), nullable=False, server_default="22.00"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_tenant_settings_tenant", "tenant_settings", ["tenant_id"], unique=True)

    # 3. Table: onboarding_progress
    if "onboarding_progress" not in existing_tables:
        op.create_table(
            "onboarding_progress",
            sa.Column("progress_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("module_slug", sa.String(64), nullable=False),
            sa.Column("is_complete", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", "module_slug", name="uq_tenant_module_progress"),
        )
        op.create_index("idx_onboarding_progress_tenant", "onboarding_progress", ["tenant_id", "module_slug"])

    # 4. Table: onboarding_steps
    if "onboarding_steps" not in existing_tables:
        op.create_table(
            "onboarding_steps",
            sa.Column("step_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("module_slug", sa.String(64), nullable=False),
            sa.Column("step_key", sa.String(64), nullable=False),
            sa.Column("step_title", sa.String(255), nullable=False),
            sa.Column("step_description", sa.Text(), nullable=True),
            sa.Column("action_type", sa.String(32), nullable=False),
            sa.Column("reference_entity", sa.String(64), nullable=True),
            sa.Column("target_route", sa.String(128), nullable=True),
            sa.Column("is_complete", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", "module_slug", "step_key", name="uq_tenant_module_step"),
        )
        op.create_index("idx_onboarding_step_tenant_module", "onboarding_steps", ["tenant_id", "module_slug", "step_key"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "onboarding_steps" in existing_tables:
        op.drop_table("onboarding_steps")
    if "onboarding_progress" in existing_tables:
        op.drop_table("onboarding_progress")
    if "tenant_settings" in existing_tables:
        op.drop_table("tenant_settings")

    tenant_columns = {c["name"] for c in inspector.get_columns("tenants")}
    for col in ["country", "industry", "timezone", "fiscal_year_start", "fiscal_year_end", "company_size", "setup_completed_at", "enabled_modules"]:
        if col in tenant_columns:
            op.drop_column("tenants", col)
