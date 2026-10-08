"""Publishes committed transactional outbox rows to Kafka with stable event IDs."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from erp.db.models.outbox import TransactionalOutbox
from erp.db.session import async_session_factory
from erp.events.producer import EventProducer

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """Claims and publishes one outbox row per database transaction.

    Row locks coordinate multiple API instances. Kafka can still receive a duplicate
    if the process dies after publish and before commit; outbox_id is the stable
    event_id consumers must use for idempotency.
    """

    def __init__(self, producer: EventProducer, poll_seconds: int = 2):
        self.producer = producer
        self.poll_seconds = poll_seconds

    async def dispatch_once(self) -> bool:
        """Publish one event and mark it processed only after Kafka acknowledges it."""
        if not self.producer.is_connected:
            return False

        async with async_session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(TransactionalOutbox)
                    .where(TransactionalOutbox.processed_at.is_(None))
                    .order_by(TransactionalOutbox.created_at, TransactionalOutbox.outbox_id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                entry = result.scalar_one_or_none()
                if entry is None:
                    return False

                payload = {
                    **entry.payload,
                    "event_id": str(entry.outbox_id),
                    "tenant_id": str(entry.tenant_id),
                    "event_type": entry.event_type,
                    "aggregate_type": entry.aggregate_type,
                    "aggregate_id": entry.aggregate_id,
                    "timestamp": entry.created_at.isoformat() if entry.created_at else datetime.now(UTC).isoformat(),
                    "trace_context": entry.trace_context,
                }
                published = await self.producer.send_event(
                    topic=entry.event_type,
                    key=f"{entry.tenant_id}:{entry.aggregate_type}:{entry.aggregate_id}",
                    value=payload,
                    headers={"event_type": entry.event_type, "outbox_id": str(entry.outbox_id)},
                )
                if not published:
                    raise RuntimeError(f"Kafka publish failed for outbox event {entry.outbox_id}")
                entry.processed_at = datetime.now(UTC)
            return True

    async def run(self, stop_event: asyncio.Event) -> None:
        """Drain committed rows until shutdown, backing off when the queue is empty."""
        while not stop_event.is_set():
            try:
                found = await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox dispatch failed; event remains available for retry")
                found = False
            if not found:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    pass
