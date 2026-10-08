"""Durable records for asynchronous orchestration workflows."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class DAGExecutionRecord(Base, TenantMixin, TimestampMixin):
    """Versioned workflow snapshot used for tenant-scoped visibility and recovery."""

    __tablename__ = "dag_execution_records"

    dag_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISPATCHED")
    workflow_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recovery_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    recovery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_dag_execution_tenant_status", "tenant_id", "status"),
    )
