"""Transactional Outbox Manager for atomic event queuing."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.outbox import TransactionalOutbox


class OutboxManager:
    """Inserts outbox events in the same database transaction as business mutations."""

    @staticmethod
    async def enqueue_event(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        trace_context: dict[str, Any] | None = None,
    ) -> TransactionalOutbox:
        """Adds an event to transactional_outbox. Will commit/rollback with the parent transaction."""
        outbox_entry = TransactionalOutbox(
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            trace_context=trace_context or {},
        )
        session.add(outbox_entry)
        await session.flush()
        return outbox_entry
