"""Tenant-scoped WhatsApp support channel persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class WhatsAppConnection(Base, TimestampMixin):
    """Connection status for one tenant's Baileys account."""

    __tablename__ = "whatsapp_connections"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DISCONNECTED")
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class WhatsAppAuthRecord(Base):
    """Encrypted Baileys credential and signal-key records."""

    __tablename__ = "whatsapp_auth_records"

    auth_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="clock_timestamp()"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "record_type", "record_id", name="uq_whatsapp_auth_record"),
        Index("idx_whatsapp_auth_tenant", "tenant_id"),
    )


class WhatsAppConversation(Base, TenantMixin, TimestampMixin):
    """A customer conversation keyed to the tenant and WhatsApp phone."""

    __tablename__ = "whatsapp_conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.issue_id", ondelete="SET NULL"), nullable=True
    )
    verified_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="SET NULL"), nullable=True
    )
    verified_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number", name="uq_whatsapp_conversation_phone"),
        Index("idx_whatsapp_conversation_queue", "tenant_id", "status", "last_message_at"),
    )


class WhatsAppMessage(Base, TenantMixin, TimestampMixin):
    """Durable inbound and outbound WhatsApp message record."""

    __tablename__ = "whatsapp_messages"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direction: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(24), nullable=False, default="RECEIVED")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_message_id", name="uq_whatsapp_provider_message"),
        Index("idx_whatsapp_messages_thread", "tenant_id", "conversation_id", "created_at"),
    )


class WhatsAppSupportToolBinding(Base, TenantMixin, TimestampMixin):
    """Tenant-level allowlist for tools exposed to the WhatsApp support agent."""

    __tablename__ = "whatsapp_support_tool_bindings"

    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("tenant_id", "tool_name", name="uq_whatsapp_support_tool_tenant"),
        Index("idx_whatsapp_support_tools_tenant", "tenant_id", "is_enabled"),
    )


class WhatsAppSupportKnowledge(Base, TenantMixin, TimestampMixin):
    """Tenant-authored text that the WhatsApp support agent can retrieve."""

    __tablename__ = "whatsapp_support_knowledge"

    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_support_knowledge_sources.source_id", ondelete="CASCADE"),
        nullable=True,
    )
    source_chunk: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_whatsapp_knowledge_tenant_title", "tenant_id", "title"),
        Index("idx_whatsapp_knowledge_source", "tenant_id", "source_id"),
    )


class WhatsAppSupportKnowledgeSource(Base, TenantMixin, TimestampMixin):
    """Tenant-owned imported source used to build WhatsApp support knowledge."""

    __tablename__ = "whatsapp_support_knowledge_sources"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="READY")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    airtable_base_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    airtable_table_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    airtable_table_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    airtable_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_whatsapp_knowledge_sources_tenant", "tenant_id", "created_at"),
        Index("idx_whatsapp_knowledge_sources_airtable", "tenant_id", "airtable_base_id", "airtable_table_id"),
    )


class WhatsAppAirtableConnection(Base, TimestampMixin):
    """Encrypted Airtable OAuth tokens for one tenant."""

    __tablename__ = "whatsapp_airtable_connections"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    encrypted_tokens: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="clock_timestamp()"
    )
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WhatsAppOTPChallenge(Base):
    """One-time identity verification challenge delivered to a registered WhatsApp number."""

    __tablename__ = "whatsapp_otp_challenges"

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="clock_timestamp()"
    )

    __table_args__ = (
        Index(
            "idx_whatsapp_otp_pending",
            "tenant_id",
            "conversation_id",
            "expires_at",
            postgresql_where=used_at.is_(None),
        ),
    )
