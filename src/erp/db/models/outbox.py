"""Transactional Outbox Model for Reliable CDC and Event Streaming (PRD Schema 2)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin


class TransactionalOutbox(Base, TenantMixin):
    """Guarantees dual-write consistency by writing event records atomically with entity mutations."""

    __tablename__ = "transactional_outbox"

    outbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Aggregate domain (e.g. GENERAL_LEDGER, STOCK_LEDGER, WORK_ORDER, INVOICE)",
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        doc="Entity ID for partition ordering",
    )
    event_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        doc="Fully-qualified domain event name (e.g. erp.finance.journal_staged)",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Complete structured event payload",
    )
    trace_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Distributed tracing context (trace_id, span_id, baggage)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when CDC connector or publisher acknowledged the event",
    )

    __table_args__ = (
        Index(
            "idx_outbox_unprocessed",
            "created_at",
            postgresql_where=processed_at.is_(None),
        ),
        Index("idx_outbox_tenant_aggregate", "tenant_id", "aggregate_type", "aggregate_id"),
    )
