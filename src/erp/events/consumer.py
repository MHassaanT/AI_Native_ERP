"""Async Kafka / Redpanda consumer with durable idempotency and DLQ handling."""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka import AIOKafkaProducer
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from erp.config import settings
from erp.db.models.events import EventDeadLetterRecord, EventProcessingRecord
from erp.db.session import async_session_factory

logger = logging.getLogger(__name__)
HANDLER_TIMEOUT_SECONDS = 120
PROCESSING_LEASE_SECONDS = 600


class EventConsumer:
    """Base consumer for subscribing to Redpanda / Kafka topics with idempotency & DLQ."""

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        handler: Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, None]],
        enable_dlq: bool = True,
        max_retries: int = 3,
    ):
        self.topics = topics
        self.group_id = group_id
        self.handler = handler
        self.enable_dlq = enable_dlq
        self.max_retries = max_retries
        self._consumer: AIOKafkaConsumer | None = None
        self._dlq_producer: AIOKafkaProducer | None = None
        self._is_running = False

    async def is_duplicate(self, event_id: str) -> bool:
        """Checks the durable event ledger; DB failure must stop processing before offset commit."""
        async with async_session_factory() as session:
            status = (
                await session.execute(
                    select(EventProcessingRecord.status).where(
                        EventProcessingRecord.consumer_group == self.group_id,
                        EventProcessingRecord.event_id == event_id,
                    )
                )
            ).scalar_one_or_none()
            return status in {"PROCESSED", "DEAD_LETTER"}

    async def record_attempt(
        self, event_id: str, tenant_id: uuid.UUID, topic: str
    ) -> uuid.UUID | None:
        """Durably claim an attempt, preserving terminal outcomes against redelivery."""
        processing_token = uuid.uuid4()
        async with async_session_factory() as session:
            statement = insert(EventProcessingRecord).values(
                consumer_group=self.group_id,
                event_id=event_id,
                tenant_id=tenant_id,
                source_topic=topic,
                status="PROCESSING",
                attempt_count=0,
                lease_expires_at=datetime.now(UTC) + timedelta(seconds=PROCESSING_LEASE_SECONDS),
                processing_token=processing_token,
            )
            statement = statement.on_conflict_do_update(
                constraint="uq_event_processing_group_event",
                set_={
                    "tenant_id": statement.excluded.tenant_id,
                    "source_topic": statement.excluded.source_topic,
                    "status": "PROCESSING",
                    "last_failure_type": None,
                    "completed_at": None,
                    "lease_expires_at": datetime.now(UTC) + timedelta(seconds=PROCESSING_LEASE_SECONDS),
                    "processing_token": processing_token,
                    "updated_at": datetime.now(UTC),
                },
                where=and_(
                    EventProcessingRecord.status.not_in(("PROCESSED", "DEAD_LETTER")),
                    or_(
                        EventProcessingRecord.status != "PROCESSING",
                        EventProcessingRecord.lease_expires_at.is_(None),
                        EventProcessingRecord.lease_expires_at <= func.clock_timestamp(),
                    ),
                ),
            )
            result = await session.execute(statement)
            await session.commit()
            return processing_token if result.rowcount == 1 else None

    async def increment_attempt(self, event_id: str, processing_token: uuid.UUID) -> None:
        async with async_session_factory() as session:
            result = await session.execute(
                update(EventProcessingRecord)
                .where(
                    EventProcessingRecord.consumer_group == self.group_id,
                    EventProcessingRecord.event_id == event_id,
                    EventProcessingRecord.status == "PROCESSING",
                    EventProcessingRecord.processing_token == processing_token,
                    EventProcessingRecord.lease_expires_at > func.clock_timestamp(),
                )
                .values(
                    attempt_count=EventProcessingRecord.attempt_count + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                raise RuntimeError("Event attempt could not be recorded durably.")
            await session.commit()

    async def _set_terminal_status(
        self,
        event_id: str,
        status: str,
        processing_token: uuid.UUID,
        failure_type: str | None = None,
    ) -> None:
        async with async_session_factory() as session:
            result = await session.execute(
                update(EventProcessingRecord)
                .where(
                    EventProcessingRecord.consumer_group == self.group_id,
                    EventProcessingRecord.event_id == event_id,
                    EventProcessingRecord.processing_token == processing_token,
                    EventProcessingRecord.status == "PROCESSING",
                )
                .values(
                    status=status,
                    last_failure_type=failure_type,
                    completed_at=datetime.now(UTC) if status in {"PROCESSED", "DEAD_LETTER"} else None,
                    lease_expires_at=None,
                    processing_token=None,
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                raise RuntimeError("Event outcome could not be written to the durable processing ledger.")
            await session.commit()

    async def mark_processed(self, event_id: str, processing_token: uuid.UUID) -> None:
        await self._set_terminal_status(event_id, "PROCESSED", processing_token)

    async def mark_dead_letter(self, event_id: str, failure_type: str, attempts: int) -> None:
        async with async_session_factory() as session:
            statement = insert(EventProcessingRecord).values(
                consumer_group=self.group_id,
                event_id=event_id,
                tenant_id=None,
                source_topic="UNKNOWN",
                status="DEAD_LETTER",
                attempt_count=attempts,
                last_failure_type=failure_type,
                completed_at=datetime.now(UTC),
            )
            statement = statement.on_conflict_do_update(
                constraint="uq_event_processing_group_event",
                set_={
                    "status": "DEAD_LETTER",
                    "last_failure_type": failure_type,
                    "completed_at": datetime.now(UTC),
                    "lease_expires_at": None,
                    "updated_at": datetime.now(UTC),
                },
                where=EventProcessingRecord.status != "PROCESSED",
            )
            await session.execute(statement)
            await session.commit()

    async def persist_dead_letter(
        self,
        event_id: str,
        tenant_id: uuid.UUID | None,
        topic: str,
        key: str,
        payload: Any,
        attempts: int,
        failure_type: str,
    ) -> None:
        async with async_session_factory() as session:
            statement = insert(EventDeadLetterRecord).values(
                consumer_group=self.group_id,
                event_id=event_id,
                tenant_id=tenant_id,
                source_topic=topic,
                partition_key=key or None,
                payload=payload if isinstance(payload, (dict, list)) else {"value": str(payload)},
                attempt_count=attempts,
                failure_type=failure_type,
                status="OPEN",
            )
            statement = statement.on_conflict_do_nothing(
                constraint="uq_event_dead_letter_group_event"
            )
            await session.execute(statement)
            await session.commit()

    async def mark_retryable(
        self, event_id: str, processing_token: uuid.UUID, failure_type: str
    ) -> None:
        await self._set_terminal_status(event_id, "RETRYABLE", processing_token, failure_type)

    async def _route_to_dlq(
        self,
        topic: str,
        key: str,
        event_id: str,
        payload: Any,
        attempts: int,
        error_type: str,
    ) -> None:
        if not self._dlq_producer:
            raise RuntimeError("Durable event DLQ producer is unavailable.")
        await self._dlq_producer.send_and_wait(
            topic=f"{topic}.DLQ",
            key=key,
            value={
                "event_id": event_id,
                "source_topic": topic,
                "payload": payload,
                "attempts": attempts,
                "failure_type": error_type,
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )

    async def start(self) -> None:
        """Starts the consumer loop with idempotency verification."""
        try:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else "",
                request_timeout_ms=5000,
            )
            if self.enable_dlq:
                self._dlq_producer = AIOKafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    client_id=f"{settings.KAFKA_CLIENT_ID}-dlq",
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    request_timeout_ms=5000,
                    enable_idempotence=True,
                )
                await self._dlq_producer.start()
            await self._consumer.start()
            self._is_running = True
            logger.info("Subscribed to %s in consumer group %s", self.topics, self.group_id)

            async for msg in self._consumer:
                payload = msg.value
                event_id = str(payload.get("event_id") or "") if isinstance(payload, dict) else ""
                fallback_id = hashlib.sha256(
                    f"{msg.topic}:{msg.partition}:{msg.offset}".encode("utf-8")
                ).hexdigest()
                stable_event_id = event_id if len(event_id) <= 128 else fallback_id
                if not stable_event_id:
                    stable_event_id = fallback_id
                tenant_id: uuid.UUID | None = None
                try:
                    if not isinstance(payload, dict):
                        raise ValueError("payload must be an object")
                    uuid.UUID(event_id)
                    tenant_id = uuid.UUID(str(payload.get("tenant_id") or ""))
                except (ValueError, TypeError, AttributeError) as err:
                    if not self.enable_dlq:
                        raise RuntimeError("Invalid event left uncommitted because its DLQ is disabled.") from err
                    await self._route_to_dlq(msg.topic, msg.key or "", fallback_id, payload, 0, type(err).__name__)
                    await self.persist_dead_letter(
                        fallback_id, None, msg.topic, msg.key or "", payload, 0, type(err).__name__
                    )
                    await self.mark_dead_letter(fallback_id, type(err).__name__, 0)
                    await self._consumer.commit()
                    continue

                if await self.is_duplicate(stable_event_id):
                    logger.debug("Durable idempotency ledger skipped event %s", stable_event_id)
                    await self._consumer.commit()
                    continue

                processing_token = await self.record_attempt(stable_event_id, tenant_id, msg.topic)
                if not processing_token:
                    if await self.is_duplicate(stable_event_id):
                        await self._consumer.commit()
                        continue
                    raise RuntimeError("Event is leased by another handler; offset left uncommitted.")

                # Process with retries
                attempts = 0
                success = False
                last_error_type = "UnknownHandlerError"
                while attempts < self.max_retries and not success:
                    attempts += 1
                    try:
                        await self.increment_attempt(stable_event_id, processing_token)
                        await asyncio.wait_for(
                            self.handler(msg.topic, msg.key or "", payload),
                            timeout=HANDLER_TIMEOUT_SECONDS,
                        )
                        success = True
                    except Exception as err:
                        last_error_type = type(err).__name__
                        logger.warning(
                            "Consumer attempt %d/%d failed for topic %s (%s)",
                            attempts,
                            self.max_retries,
                            msg.topic,
                            type(err).__name__,
                        )
                        if attempts < self.max_retries:
                            await asyncio.sleep(0.2 * attempts)

                if not success and self.enable_dlq:
                    logger.error("Event %s failed after %d retries. Routing to DLQ.", event_id, self.max_retries)
                    await self._route_to_dlq(
                        msg.topic, msg.key or "", stable_event_id, payload, attempts,
                        last_error_type,
                    )
                    await self.persist_dead_letter(
                        stable_event_id, tenant_id, msg.topic, msg.key or "", payload,
                        attempts, last_error_type,
                    )
                    await self._set_terminal_status(
                        stable_event_id, "DEAD_LETTER", processing_token, last_error_type
                    )
                    await self._consumer.commit()
                elif not success:
                    # Leave the offset uncommitted so Kafka can redeliver it.
                    await self.mark_retryable(stable_event_id, processing_token, last_error_type)
                    raise RuntimeError("Event handler retries exhausted; offset left uncommitted.")
                else:
                    await self.mark_processed(stable_event_id, processing_token)
                    await self._consumer.commit()
        except Exception as e:
            logger.warning("EventConsumer stopped (%s).", type(e).__name__)
            self._is_running = False
            if self._consumer:
                try:
                    await self._consumer.stop()
                except Exception:
                    pass
                self._consumer = None
            if self._dlq_producer:
                try:
                    await self._dlq_producer.stop()
                except Exception:
                    pass
                self._dlq_producer = None

    async def stop(self) -> None:
        """Stops the consumer."""
        if self._consumer and self._is_running:
            try:
                await self._consumer.stop()
            except Exception as e:
                logger.debug("Error stopping consumer: %s", e)
            finally:
                self._is_running = False
        if self._dlq_producer:
            try:
                await self._dlq_producer.stop()
            except Exception:
                pass
            self._dlq_producer = None
