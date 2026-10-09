"""Add the tenant-scoped Baileys WhatsApp support channel.

Revision ID: 017_whatsapp_support_channel
Revises: 016_hr_email_pool
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "017_whatsapp_support_channel"
down_revision: str | None = "016_hr_email_pool"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_connections",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="DISCONNECTED", nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('DISCONNECTED', 'CONNECTING', 'QR_PENDING', 'CONNECTED', 'ERROR')",
            name="ck_whatsapp_connection_status",
        ),
    )
    op.create_table(
        "whatsapp_auth_records",
        sa.Column(
            "auth_record_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("auth_record_id"),
        sa.UniqueConstraint(
            "tenant_id", "record_type", "record_id", name="uq_whatsapp_auth_record"
        ),
    )
    op.create_index("idx_whatsapp_auth_tenant", "whatsapp_auth_records", ["tenant_id"])

    op.create_table(
        "whatsapp_conversations",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="ACTIVE", nullable=False),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'HUMAN_HANDOFF', 'CLOSED')",
            name="ck_whatsapp_conversation_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.issue_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_lead_id"], ["leads.lead_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("conversation_id"),
        sa.UniqueConstraint("tenant_id", "phone_number", name="uq_whatsapp_conversation_phone"),
    )
    op.create_index(
        "idx_whatsapp_conversation_queue",
        "whatsapp_conversations",
        ["tenant_id", "status", "last_message_at"],
    )

    op.create_table(
        "whatsapp_messages",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(length=24), server_default="RECEIVED", nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("direction IN ('INBOUND', 'OUTBOUND')", name="ck_whatsapp_message_direction"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.conversation_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint(
            "tenant_id", "provider_message_id", name="uq_whatsapp_provider_message"
        ),
    )
    op.create_index(
        "idx_whatsapp_messages_thread",
        "whatsapp_messages",
        ["tenant_id", "conversation_id", "created_at"],
    )

    op.create_table(
        "whatsapp_support_tool_bindings",
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint("tenant_id", "tool_name", name="uq_whatsapp_support_tool_tenant"),
    )
    op.create_index(
        "idx_whatsapp_support_tools_tenant",
        "whatsapp_support_tool_bindings",
        ["tenant_id", "is_enabled"],
    )
    op.create_table(
        "whatsapp_support_knowledge",
        sa.Column(
            "knowledge_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("knowledge_id"),
    )
    op.create_index(
        "idx_whatsapp_knowledge_tenant_title",
        "whatsapp_support_knowledge",
        ["tenant_id", "title"],
    )

    op.create_table(
        "whatsapp_otp_challenges",
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_whatsapp_otp_attempts"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.conversation_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.lead_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("challenge_id"),
    )
    op.create_index(
        "idx_whatsapp_otp_pending",
        "whatsapp_otp_challenges",
        ["tenant_id", "conversation_id", "expires_at"],
        postgresql_where=sa.text("used_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_whatsapp_otp_pending", table_name="whatsapp_otp_challenges")
    op.drop_table("whatsapp_otp_challenges")
    op.drop_index("idx_whatsapp_knowledge_tenant_title", table_name="whatsapp_support_knowledge")
    op.drop_table("whatsapp_support_knowledge")
    op.drop_index("idx_whatsapp_support_tools_tenant", table_name="whatsapp_support_tool_bindings")
    op.drop_table("whatsapp_support_tool_bindings")
    op.drop_index("idx_whatsapp_messages_thread", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
    op.drop_index("idx_whatsapp_conversation_queue", table_name="whatsapp_conversations")
    op.drop_table("whatsapp_conversations")
    op.drop_index("idx_whatsapp_auth_tenant", table_name="whatsapp_auth_records")
    op.drop_table("whatsapp_auth_records")
    op.drop_table("whatsapp_connections")
