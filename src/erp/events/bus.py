"""In-Process Asynchronous Pub/Sub Event Bus."""

import asyncio
import fnmatch
import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, None]]


class AsyncEventBus:
    """Provides in-process asynchronous topic pub/sub dispatch with wildcard matching."""

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Subscribes an async handler to a topic pattern (supports * wildcards)."""
        self._subscribers.setdefault(topic_pattern, []).append(handler)
        logger.debug("Subscribed %s to %s", handler.__name__, topic_pattern)

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Removes a handler subscription."""
        if topic_pattern in self._subscribers and handler in self._subscribers[topic_pattern]:
            self._subscribers[topic_pattern].remove(handler)

    async def publish(self, topic: str, key: str, payload: dict[str, Any]) -> int:
        """Dispatches an event payload to all matching subscribers."""
        matched_handlers: list[EventHandler] = []
        for pattern, handlers in self._subscribers.items():
            if pattern == topic or fnmatch.fnmatch(topic, pattern):
                matched_handlers.extend(handlers)

        if not matched_handlers:
            return 0

        dispatched = 0
        tasks = []
        for handler in matched_handlers:
            tasks.append(self._invoke_handler(handler, topic, key, payload))
            dispatched += 1

        await asyncio.gather(*tasks, return_exceptions=True)
        return dispatched

    async def _invoke_handler(
        self, handler: EventHandler, topic: str, key: str, payload: dict[str, Any]
    ) -> None:
        try:
            await handler(topic, key, payload)
        except Exception as e:
            logger.error("Event handler %s failed for topic %s: %s", getattr(handler, "__name__", str(handler)), topic, e, exc_info=True)


async_event_bus = AsyncEventBus()
