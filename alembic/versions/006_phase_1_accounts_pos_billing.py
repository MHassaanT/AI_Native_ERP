"""006 Phase 1 Accounts, POS, and Billing Expansion

Revision ID: 006_phase_1_billing
Revises: 005_onboarding_and_setup
Create Date: 2026-09-29 19:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_phase_1_billing"
down_revision: str | None = "005_onboarding_and_setup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Credit Notes
    if "credit_notes" not in existing_tables:
        op.create_table(
            "credit_notes",
            sa.Column("credit_note_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("credit_note_number", sa.String(64), nullable=False),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.invoice_id"), nullable=True),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("posting_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("subtotal", sa.Numeric(18, 4), nullable=False),
            sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("total_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="POSTED"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_cn_tenant_number", "credit_notes", ["tenant_id", "credit_note_number"], unique=True)

    if "credit_note_items" not in existing_tables:
        op.create_table(
            "credit_note_items",
            sa.Column("cn_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("credit_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("credit_notes.credit_note_id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
            sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )

    # 2. Debit Notes
    if "debit_notes" not in existing_tables:
        op.create_table(
            "debit_notes",
            sa.Column("debit_note_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("debit_note_number", sa.String(64), nullable=False),
            sa.Column("supplier_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("supplier_invoices.invoice_id"), nullable=True),
            sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.supplier_id"), nullable=False),
            sa.Column("posting_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("subtotal", sa.Numeric(18, 4), nullable=False),
            sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("total_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="POSTED"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_dn_debit_tenant_number", "debit_notes", ["tenant_id", "debit_note_number"], unique=True)

    if "debit_note_items" not in existing_tables:
        op.create_table(
            "debit_note_items",
            sa.Column("dn_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("debit_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("debit_notes.debit_note_id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
            sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )

    # 3. POS System
    if "pos_profiles" not in existing_tables:
        op.create_table(
            "pos_profiles",
            sa.Column("profile_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("profile_name", sa.String(128), nullable=False),
            sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.warehouse_id"), nullable=False),
            sa.Column("cost_center", sa.String(64), nullable=False, server_default="Main - CC"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("income_account", sa.String(32), nullable=False, server_default="4000-SALES-REVENUE"),
            sa.Column("expense_account", sa.String(32), nullable=False, server_default="5000-COGS"),
            sa.Column("allow_discount_change", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("allow_rate_change", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_pos_profile_name", "pos_profiles", ["tenant_id", "profile_name"], unique=True)

    if "pos_opening_entries" not in existing_tables:
        op.create_table(
            "pos_opening_entries",
            sa.Column("opening_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_profiles.profile_id"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
            sa.Column("period_start_date", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("opening_float_cash", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_pos_opening_status", "pos_opening_entries", ["tenant_id", "user_id", "status"])

    if "pos_closing_entries" not in existing_tables:
        op.create_table(
            "pos_closing_entries",
            sa.Column("closing_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("opening_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_opening_entries.opening_id"), nullable=False),
            sa.Column("period_end_date", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("total_sales_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("total_collected_cash", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("total_collected_card", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("total_collected_other", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("expected_cash", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("actual_counted_cash", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("cash_variance", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("status", sa.String(32), nullable=False, server_default="SUBMITTED"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )

    if "pos_invoices" not in existing_tables:
        op.create_table(
            "pos_invoices",
            sa.Column("pos_invoice_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("pos_invoice_number", sa.String(64), nullable=False),
            sa.Column("opening_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_opening_entries.opening_id"), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("posting_date", sa.Date(), nullable=False),
            sa.Column("posting_time", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("subtotal", sa.Numeric(18, 4), nullable=False),
            sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("grand_total", sa.Numeric(18, 4), nullable=False),
            sa.Column("paid_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("change_amount", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
            sa.Column("payment_method", sa.String(32), nullable=False, server_default="CASH"),
            sa.Column("payment_details", postgresql.JSONB(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="PAID"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_pos_inv_tenant_num", "pos_invoices", ["tenant_id", "pos_invoice_number"], unique=True)

    if "pos_invoice_items" not in existing_tables:
        op.create_table(
            "pos_invoice_items",
            sa.Column("pos_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("pos_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_invoices.pos_invoice_id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
            sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
            sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )

    # 4. Subscriptions
    if "subscription_plans" not in existing_tables:
        op.create_table(
            "subscription_plans",
            sa.Column("plan_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_name", sa.String(128), nullable=False),
            sa.Column("billing_interval", sa.String(32), nullable=False, server_default="MONTHLY"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("cost", sa.Numeric(18, 4), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_sub_plan_name", "subscription_plans", ["tenant_id", "plan_name"], unique=True)

    if "subscriptions" not in existing_tables:
        op.create_table(
            "subscriptions",
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.plan_id"), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("next_billing_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("cancel_reason", sa.String(255), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )

    # 5. Dunning
    if "dunning_types" not in existing_tables:
        op.create_table(
            "dunning_types",
            sa.Column("dunning_type_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("dunning_type_name", sa.String(64), nullable=False),
            sa.Column("overdue_days", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("fee_amount", sa.Numeric(18, 4), nullable=False, server_default="25.0000"),
            sa.Column("interest_rate_pct", sa.Numeric(5, 2), nullable=False, server_default="2.50"),
            sa.Column("message_body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_dunning_type_name", "dunning_types", ["tenant_id", "dunning_type_name"], unique=True)

    if "dunning_notices" not in existing_tables:
        op.create_table(
            "dunning_notices",
            sa.Column("notice_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("notice_number", sa.String(64), nullable=False),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.invoice_id"), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
            sa.Column("dunning_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dunning_types.dunning_type_id"), nullable=False),
            sa.Column("posting_date", sa.Date(), nullable=False),
            sa.Column("overdue_days", sa.Integer(), nullable=False),
            sa.Column("outstanding_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("fee_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("interest_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("total_dunning_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="ISSUED"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_dunning_tenant_number", "dunning_notices", ["tenant_id", "notice_number"], unique=True)

    # 6. Budgets
    if "budgets" not in existing_tables:
        op.create_table(
            "budgets",
            sa.Column("budget_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("budget_name", sa.String(128), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("cost_center", sa.String(64), nullable=False),
            sa.Column("account_code", sa.String(32), nullable=False),
            sa.Column("budget_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("action_on_exceed", sa.String(16), nullable=False, server_default="WARN"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_budget_lookup", "budgets", ["tenant_id", "fiscal_year", "cost_center", "account_code"])

    # 7. Tax Withholding
    if "tax_withholding_categories" not in existing_tables:
        op.create_table(
            "tax_withholding_categories",
            sa.Column("category_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
            sa.Column("category_name", sa.String(128), nullable=False),
            sa.Column("section_code", sa.String(32), nullable=False),
            sa.Column("rate_pct", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
            sa.Column("single_threshold", sa.Numeric(18, 4), nullable=False, server_default="30000.0000"),
            sa.Column("cumulative_threshold", sa.Numeric(18, 4), nullable=False, server_default="100000.0000"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        )
        op.create_index("idx_tds_cat_name", "tax_withholding_categories", ["tenant_id", "category_name"], unique=True)


def downgrade() -> None:
    pass
