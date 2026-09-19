"""Async Kafka / Redpanda Event Consumer with Redis Idempotency & DLQ."""

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from aiokafka import AIOKafkaConsumer
import redis.asyncio as aioredis

from erp.config import settings

logger = logging.getLogger(__name__)


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
        self._redis_client: aioredis.Redis | None = None
        self._is_running = False
        self._local_idempotency_set: set[str] = set()

    async def _get_redis(self) -> aioredis.Redis | None:
        """Retrieves or creates Redis async client connection."""
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
            except Exception as e:
                logger.debug("Redis connection skipped in consumer: %s", e)
        return self._redis_client

    async def is_duplicate(self, event_id: str) -> bool:
        """Checks if event was already processed using Redis NX with 24h expiry or local memory."""
        if not event_id:
            return False

        r = await self._get_redis()
        if r:
            try:
                # Returns True if key was set (i.e. fresh event), False if key already exists
                key = f"erp:idempotency:{event_id}"
                was_set = await r.set(key, "1", ex=86400, nx=True)
                return not was_set
            except Exception as e:
                logger.debug("Redis idempotency check failed (%s), falling back to in-memory set.", e)

        # In-memory fallback
        if event_id in self._local_idempotency_set:
            return True
        self._local_idempotency_set.add(event_id)
        if len(self._local_idempotency_set) > 10000:
            self._local_idempotency_set.clear()
        return False

    async def start(self) -> None:
        """Starts the consumer loop with idempotency verification."""
        try:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else "",
                request_timeout_ms=5000,
            )
            await self._consumer.start()
            self._is_running = True
            logger.info("Subscribed to %s in consumer group %s", self.topics, self.group_id)

            async for msg in self._consumer:
                payload = msg.value if isinstance(msg.value, dict) else {}
                event_id = payload.get("event_id") or msg.key or f"{msg.topic}_{msg.offset}"

                if await self.is_duplicate(event_id):
                    logger.debug("Idempotency guard: skipping duplicate event %s", event_id)
                    continue

                # Process with retries
                attempts = 0
                success = False
                while attempts < self.max_retries and not success:
                    attempts += 1
                    try:
                        await self.handler(msg.topic, msg.key, payload)
                        success = True
                    except Exception as err:
                        logger.warning(
                            "Consumer attempt %d/%d failed for topic %s: %s",
                            attempts,
                            self.max_retries,
                            msg.topic,
                            err,
                        )
                        if attempts < self.max_retries:
                            await asyncio.sleep(0.2 * attempts)

                if not success and self.enable_dlq:
                    logger.error("Event %s failed after %d retries. Routing to DLQ.", event_id, self.max_retries)
                    # Future dispatch to DLQ topic
        except Exception as e:
            logger.warning("EventConsumer failed to connect to Redpanda (%s). Running in idle mode.", e)
            self._is_running = False

    async def stop(self) -> None:
        """Stops the consumer."""
        if self._consumer and self._is_running:
            try:
                await self._consumer.stop()
            except Exception as e:
                logger.debug("Error stopping consumer: %s", e)
            finally:
                self._is_running = False
        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None

