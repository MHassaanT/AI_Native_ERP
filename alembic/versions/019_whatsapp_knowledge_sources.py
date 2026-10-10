"""Add importable knowledge sources for WhatsApp support.

Revision ID: 019_whatsapp_knowledge_sources
Revises: 018_hr_talent_pool_review
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "019_whatsapp_knowledge_sources"
down_revision: str | None = "018_hr_talent_pool_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_support_knowledge_sources",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="READY", nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("airtable_base_id", sa.String(length=64), nullable=True),
        sa.Column("airtable_table_id", sa.String(length=64), nullable=True),
        sa.Column("airtable_table_name", sa.String(length=255), nullable=True),
        sa.Column("airtable_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
        sa.CheckConstraint(
            "source_type IN ('FILE', 'WEB', 'AIRTABLE')",
            name="ck_whatsapp_knowledge_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('READY', 'FAILED')",
            name="ck_whatsapp_knowledge_source_status",
        ),
    )
    op.create_index(
        "idx_whatsapp_knowledge_sources_tenant",
        "whatsapp_support_knowledge_sources",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_whatsapp_knowledge_sources_airtable",
        "whatsapp_support_knowledge_sources",
        ["tenant_id", "airtable_base_id", "airtable_table_id"],
    )
    op.create_table(
        "whatsapp_airtable_connections",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_tokens", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("is_connected", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.add_column(
        "whatsapp_support_knowledge",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "whatsapp_support_knowledge",
        sa.Column("source_chunk", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_whatsapp_knowledge_source",
        "whatsapp_support_knowledge",
        "whatsapp_support_knowledge_sources",
        ["source_id"],
        ["source_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_whatsapp_knowledge_source",
        "whatsapp_support_knowledge",
        ["tenant_id", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_whatsapp_knowledge_source", table_name="whatsapp_support_knowledge")
    op.drop_constraint(
        "fk_whatsapp_knowledge_source",
        "whatsapp_support_knowledge",
        type_="foreignkey",
    )
    op.drop_column("whatsapp_support_knowledge", "source_chunk")
    op.drop_column("whatsapp_support_knowledge", "source_id")
    op.drop_table("whatsapp_airtable_connections")
    op.drop_index(
        "idx_whatsapp_knowledge_sources_airtable",
        table_name="whatsapp_support_knowledge_sources",
    )
    op.drop_index(
        "idx_whatsapp_knowledge_sources_tenant",
        table_name="whatsapp_support_knowledge_sources",
    )
    op.drop_table("whatsapp_support_knowledge_sources")
