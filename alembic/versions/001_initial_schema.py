"""001 Initial Schema for AI-Native ERP

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-17 19:50:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable PostgreSQL Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # 2. General Ledger Core Table (PRD Schema 1)
    op.create_table(
        "general_ledger_entries",
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=32), nullable=False),
        sa.Column("cost_center", sa.String(length=64), nullable=False),
        sa.Column(
            "debit_amount",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "credit_amount",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column(
            "exchange_rate",
            sa.Numeric(precision=12, scale=6),
            server_default="1.000000",
            nullable=False,
        ),
        sa.Column("source_document_type", sa.String(length=64), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "period_closing_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("debit_amount >= 0", name="chk_positive_debit"),
        sa.CheckConstraint("credit_amount >= 0", name="chk_positive_credit"),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="chk_single_sided_line",
        ),
    )
    op.create_index(
        "idx_gl_account_period",
        "general_ledger_entries",
        ["tenant_id", "account_code", "fiscal_year", "fiscal_period"],
    )
    op.create_index(
        "idx_gl_transaction_id", "general_ledger_entries", ["tenant_id", "transaction_id"]
    )
    op.create_index("idx_gl_tenant_id", "general_ledger_entries", ["tenant_id"])

    # 3. Chart of Accounts & Cost Centers & Fiscal Periods
    op.create_table(
        "chart_of_accounts",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=128), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("parent_account_code", sa.String(length=32), nullable=True),
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
        "idx_coa_tenant_code", "chart_of_accounts", ["tenant_id", "account_code"], unique=True
    )

    op.create_table(
        "cost_centers",
        sa.Column(
            "cost_center_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cost_center_code", sa.String(length=64), nullable=False),
        sa.Column("cost_center_name", sa.String(length=128), nullable=False),
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
        "idx_cc_tenant_code", "cost_centers", ["tenant_id", "cost_center_code"], unique=True
    )

    op.create_table(
        "fiscal_periods",
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        "idx_fiscal_period_tenant_year_period",
        "fiscal_periods",
        ["tenant_id", "fiscal_year", "fiscal_period"],
        unique=True,
    )

    # 4. Transactional Outbox (PRD Schema 2)
    op.create_table(
        "transactional_outbox",
        sa.Column(
            "outbox_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_outbox_unprocessed",
        "transactional_outbox",
        ["created_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index(
        "idx_outbox_tenant_aggregate",
        "transactional_outbox",
        ["tenant_id", "aggregate_type", "aggregate_id"],
    )

    # 5. Agent Audit Logs (PRD Schema 3)
    op.create_table(
        "agent_audit_logs",
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("subagent_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("model_provider", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_template_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_context_hashes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("baml_function_called", sa.String(length=128), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_raw_output", sa.Text(), nullable=False),
        sa.Column(
            "parsed_structured_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "evaluated_guardrail_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "human_in_the_loop_approval",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("database_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=False),
        sa.Column("previous_record_hash", sa.String(length=64), nullable=True),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    )
    op.create_index("idx_audit_trace", "agent_audit_logs", ["tenant_id", "trace_id"])
    op.create_index("idx_audit_agent", "agent_audit_logs", ["tenant_id", "agent_id", "timestamp"])

    # 6. Semantic Document Embeddings (PRD Schema 4)
    op.create_table(
        "semantic_document_embeddings",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_chunk", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX idx_vector_hnsw ON semantic_document_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )
    op.create_index(
        "idx_doc_tenant_entity",
        "semantic_document_embeddings",
        ["tenant_id", "entity_type", "entity_id"],
    )

    # 7. Inventory Domain
    op.create_table(
        "items",
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stock_uom", sa.String(length=32), server_default="Nos", nullable=False),
        sa.Column("is_stock_item", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_sales_item", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_purchase_item", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("valuation_method", sa.String(length=32), server_default="FIFO", nullable=False),
        sa.Column(
            "standard_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "reorder_level",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
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
    op.create_index("idx_item_tenant_code", "items", ["tenant_id", "item_code"], unique=True)

    op.create_table(
        "warehouses",
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_code", sa.String(length=64), nullable=False),
        sa.Column("warehouse_name", sa.String(length=128), nullable=False),
        sa.Column("parent_warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_quarantine", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        "idx_wh_tenant_code", "warehouses", ["tenant_id", "warehouse_code"], unique=True
    )

    op.create_table(
        "stock_ledger_entries",
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("posting_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.warehouse_id"),
            nullable=False,
        ),
        sa.Column("actual_qty", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("qty_after_transaction", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "incoming_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "outgoing_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "valuation_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "stock_value_difference",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("source_document_type", sa.String(length=64), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_cancelled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_sle_item_wh_datetime",
        "stock_ledger_entries",
        ["tenant_id", "item_id", "warehouse_id", "posting_datetime"],
    )

    op.create_table(
        "stock_levels",
        sa.Column(
            "stock_level_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.warehouse_id"),
            nullable=False,
        ),
        sa.Column(
            "current_qty",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "reserved_qty",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "available_qty",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "valuation_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
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
        "idx_stock_level_tenant_item_wh",
        "stock_levels",
        ["tenant_id", "item_id", "warehouse_id"],
        unique=True,
    )

    # 8. Purchasing Domain
    op.create_table(
        "suppliers",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_code", sa.String(length=64), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column(
            "otif_score", sa.Numeric(precision=5, scale=2), server_default="100.00", nullable=False
        ),
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
    op.create_index("idx_sup_tenant_code", "suppliers", ["tenant_id", "supplier_code"], unique=True)

    op.create_table(
        "purchase_orders",
        sa.Column(
            "po_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("po_number", sa.String(length=64), nullable=False),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.supplier_id"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column(
            "subtotal", sa.Numeric(precision=18, scale=4), server_default="0.0000", nullable=False
        ),
        sa.Column(
            "tax_amount", sa.Numeric(precision=18, scale=4), server_default="0.0000", nullable=False
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
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
        "idx_po_tenant_number", "purchase_orders", ["tenant_id", "po_number"], unique=True
    )

    op.create_table(
        "purchase_order_items",
        sa.Column(
            "item_line_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "po_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.po_id"),
            nullable=False,
        ),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=4), nullable=False),
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

    op.create_table(
        "goods_receipt_notes",
        sa.Column(
            "grn_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grn_number", sa.String(length=64), nullable=False),
        sa.Column(
            "po_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.po_id"),
            nullable=True,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.supplier_id"),
            nullable=False,
        ),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="COMPLETED", nullable=False),
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
        "idx_grn_tenant_number", "goods_receipt_notes", ["tenant_id", "grn_number"], unique=True
    )

    op.create_table(
        "supplier_invoices",
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.supplier_id"),
            nullable=False,
        ),
        sa.Column(
            "po_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.po_id"),
            nullable=True,
        ),
        sa.Column(
            "grn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("goods_receipt_notes.grn_id"),
            nullable=True,
        ),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "matching_status", sa.String(length=32), server_default="UNMATCHED", nullable=False
        ),
        sa.Column(
            "variance_percentage",
            sa.Numeric(precision=8, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
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
        "idx_sinv_tenant_number",
        "supplier_invoices",
        ["tenant_id", "supplier_id", "invoice_number"],
        unique=True,
    )

    # 9. Manufacturing Domain
    op.create_table(
        "workstations",
        sa.Column(
            "workstation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workstation_code", sa.String(length=64), nullable=False),
        sa.Column("workstation_name", sa.String(length=128), nullable=False),
        sa.Column(
            "hourly_rate",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default="OPERATIONAL", nullable=False),
        sa.Column("iot_device_id", sa.String(length=128), nullable=True),
        sa.Column(
            "health_score",
            sa.Numeric(precision=5, scale=2),
            server_default="100.00",
            nullable=False,
        ),
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
        "idx_ws_tenant_code", "workstations", ["tenant_id", "workstation_code"], unique=True
    )

    op.create_table(
        "boms",
        sa.Column(
            "bom_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bom_number", sa.String(length=64), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column(
            "quantity", sa.Numeric(precision=18, scale=4), server_default="1.0000", nullable=False
        ),
        sa.Column(
            "total_cost", sa.Numeric(precision=18, scale=4), server_default="0.0000", nullable=False
        ),
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
    op.create_index("idx_bom_tenant_number", "boms", ["tenant_id", "bom_number"], unique=True)

    op.create_table(
        "bom_items",
        sa.Column(
            "bom_item_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.bom_id"), nullable=False
        ),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "rate", sa.Numeric(precision=18, scale=4), server_default="0.0000", nullable=False
        ),
        sa.Column(
            "amount", sa.Numeric(precision=18, scale=4), server_default="0.0000", nullable=False
        ),
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

    op.create_table(
        "work_orders",
        sa.Column(
            "work_order_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_number", sa.String(length=64), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column(
            "bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.bom_id"), nullable=True
        ),
        sa.Column(
            "workstation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workstations.workstation_id"),
            nullable=True,
        ),
        sa.Column("planned_quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "produced_quantity",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("planned_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
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
        "idx_wo_tenant_number", "work_orders", ["tenant_id", "work_order_number"], unique=True
    )

    op.create_table(
        "maintenance_tickets",
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.String(length=64), nullable=False),
        sa.Column(
            "workstation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workstations.workstation_id"),
            nullable=False,
        ),
        sa.Column(
            "trigger_type",
            sa.String(length=32),
            server_default="PREDICTIVE_ANOMALY",
            nullable=False,
        ),
        sa.Column("fault_code", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="OPEN", nullable=False),
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
        "idx_maint_tenant_number",
        "maintenance_tickets",
        ["tenant_id", "ticket_number"],
        unique=True,
    )

    # 10. Sales Domain
    op.create_table(
        "customers",
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_code", sa.String(length=64), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "credit_limit",
            sa.Numeric(precision=18, scale=4),
            server_default="10000.0000",
            nullable=False,
        ),
        sa.Column(
            "lifetime_value",
            sa.Numeric(precision=18, scale=4),
            server_default="0.0000",
            nullable=False,
        ),
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
        "idx_cust_tenant_code", "customers", ["tenant_id", "customer_code"], unique=True
    )

    op.create_table(
        "sales_quotations",
        sa.Column(
            "quotation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_number", sa.String(length=64), nullable=False),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id"),
            nullable=False,
        ),
        sa.Column("quotation_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "contribution_margin_pct",
            sa.Numeric(precision=5, scale=2),
            server_default="22.00",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
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
        "idx_quote_tenant_number",
        "sales_quotations",
        ["tenant_id", "quotation_number"],
        unique=True,
    )

    op.create_table(
        "sales_orders",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(length=64), nullable=False),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="CONFIRMED", nullable=False),
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
        "idx_so_tenant_number", "sales_orders", ["tenant_id", "order_number"], unique=True
    )

    op.create_table(
        "sales_order_items",
        sa.Column(
            "order_item_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sales_orders.order_id"),
            nullable=False,
        ),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.item_id"), nullable=False
        ),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=4), nullable=False),
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

    # 11. HR & Workforce Domain
    op.create_table(
        "employees",
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=64), nullable=False),
        sa.Column("last_name", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("certifications", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("max_weekly_hours", sa.Integer(), server_default="48", nullable=False),
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
    op.create_index("idx_emp_tenant_code", "employees", ["tenant_id", "employee_code"], unique=True)

    op.create_table(
        "shift_schedules",
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_code", sa.String(length=64), nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.employee_id"),
            nullable=False,
        ),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="SCHEDULED", nullable=False),
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
        "idx_shift_tenant_emp_date", "shift_schedules", ["tenant_id", "employee_id", "shift_date"]
    )

    op.create_table(
        "expense_claims",
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_number", sa.String(length=64), nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.employee_id"),
            nullable=False,
        ),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("merchant_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), server_default="MEALS", nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("receipt_image_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="SUBMITTED", nullable=False),
        sa.Column("auto_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("violation_notes", sa.Text(), nullable=True),
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
        "idx_exp_tenant_number", "expense_claims", ["tenant_id", "claim_number"], unique=True
    )


def downgrade() -> None:
    op.drop_table("expense_claims")
    op.drop_table("shift_schedules")
    op.drop_table("employees")
    op.drop_table("sales_order_items")
    op.drop_table("sales_orders")
    op.drop_table("sales_quotations")
    op.drop_table("customers")
    op.drop_table("maintenance_tickets")
    op.drop_table("work_orders")
    op.drop_table("bom_items")
    op.drop_table("boms")
    op.drop_table("workstations")
    op.drop_table("supplier_invoices")
    op.drop_table("goods_receipt_notes")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("suppliers")
    op.drop_table("stock_levels")
    op.drop_table("stock_ledger_entries")
    op.drop_table("warehouses")
    op.drop_table("items")
    op.drop_table("semantic_document_embeddings")
    op.drop_table("agent_audit_logs")
    op.drop_table("transactional_outbox")
    op.drop_table("fiscal_periods")
    op.drop_table("cost_centers")
    op.drop_table("chart_of_accounts")
    op.drop_table("general_ledger_entries")
