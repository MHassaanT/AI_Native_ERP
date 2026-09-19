"""Immutable Agent Audit Log with Cryptographic Lineage (PRD Schema 3)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin


class AgentAuditLog(Base, TenantMixin):
    """Tamper-evident cryptographic ledger recording full multi-agent LLM reasoning context."""

    __tablename__ = "agent_audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subagent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_template_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_context_hashes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    baml_function_called: Mapped[str] = mapped_column(String(128), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_structured_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluated_guardrail_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    human_in_the_loop_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    database_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    execution_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256(record_fields + previous_record_hash)",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_audit_trace", "tenant_id", "trace_id"),
        Index("idx_audit_agent", "tenant_id", "agent_id", "timestamp"),
    )
