"""Async Kafka / Redpanda Event Producer (PRD §Event Streaming & MAS Mesh)."""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer

from erp.config import settings

logger = logging.getLogger(__name__)

# Standard PRD Domain Event Topics
TOPIC_RFQ_INBOUND = "erp.crm.rfq.inbound"
TOPIC_PO_CREATED = "erp.supplychain.po.created"
TOPIC_WORK_ORDER_DISPATCHED = "erp.manufacturing.work_order.dispatched"
TOPIC_JOURNAL_ENTRY_POSTED = "erp.general_ledger.journal_entry.posted"
TOPIC_QUALITY_ANOMALY = "erp.quality.inspection.anomaly"


def make_partition_key(tenant_id: str | uuid.UUID, entity_type: str, entity_id: str) -> str:
    """Generates standard deterministic partition key: tenant_id:entity_type:entity_id."""
    return f"{tenant_id}:{entity_type}:{entity_id}"


class EventProducer:
    """Publishes structured events to Redpanda / Kafka topics with in-memory fallback."""

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None
        self._is_started = False
        self.event_log: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Initializes and connects the Kafka producer."""
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                client_id=settings.KAFKA_CLIENT_ID,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                request_timeout_ms=3000,
            )
            await self._producer.start()
            self._is_started = True
            logger.info("Connected to Redpanda/Kafka broker at %s", settings.KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.warning("Redpanda broker unreachable (%s). EventProducer operating with in-memory bus.", e)
            self._is_started = False

    async def stop(self) -> None:
        """Shuts down the producer."""
        if self._producer and self._is_started:
            try:
                await self._producer.stop()
            except Exception as e:
                logger.debug("Error during producer stop: %s", e)
            finally:
                self._is_started = False

    async def send_event(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Sends an event with partition key to Redpanda / local event store."""
        event_record = {
            "event_id": value.get("event_id", f"evt_{uuid.uuid4().hex[:12]}"),
            "topic": topic,
            "partition_key": key,
            "timestamp": value.get("timestamp", datetime.now(UTC).isoformat()),
            "payload": value,
            "headers": headers or {},
            "status": "PUBLISHED",
        }
        self.event_log.insert(0, event_record)
        if len(self.event_log) > 200:
            self.event_log.pop()

        if not self._is_started or not self._producer:
            logger.info("[LOCAL STREAM] Topic: %s | Key: %s | ID: %s", topic, key, event_record["event_id"])
            return True

        try:
            formatted_headers = [(k, v.encode("utf-8")) for k, v in (headers or {}).items()]
            await self._producer.send_and_wait(
                topic=topic,
                key=key,
                value=value,
                headers=formatted_headers if formatted_headers else None,
            )
            return True
        except Exception as e:
            logger.error("Failed to publish event to Redpanda topic %s: %s (Buffered in local event log)", topic, e)
            return False

    def get_recent_events(self, topic: str | None = None) -> list[dict[str, Any]]:
        """Returns recent in-memory event stream records for telemetry and UI verification."""
        if not topic:
            return self.event_log
        return [e for e in self.event_log if e["topic"] == topic]


event_producer = EventProducer()

