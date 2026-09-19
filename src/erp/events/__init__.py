"""Event Streaming Subsystem."""

from erp.events.consumer import EventConsumer
from erp.events.outbox import OutboxManager
from erp.events.producer import EventProducer, event_producer
from erp.events.schemas import (
    BaseEvent,
    JournalPostedEvent,
    MachineFaultEvent,
    StockMovementEvent,
)
from erp.events.topics import (
    ALL_TOPICS,
    TOPIC_AUDIT_EVENTS,
    TOPIC_CRM_EVENTS,
    TOPIC_FINANCE_JOURNAL_EVENTS,
    TOPIC_PRODUCTION_TELEMETRY,
    TOPIC_SUPPLY_CHAIN_EVENTS,
    TOPIC_WORKFORCE_EVENTS,
    TopicConfig,
)

__all__ = [
    "OutboxManager",
    "EventProducer",
    "event_producer",
    "EventConsumer",
    "TopicConfig",
    "ALL_TOPICS",
    "TOPIC_FINANCE_JOURNAL_EVENTS",
    "TOPIC_SUPPLY_CHAIN_EVENTS",
    "TOPIC_PRODUCTION_TELEMETRY",
    "TOPIC_WORKFORCE_EVENTS",
    "TOPIC_CRM_EVENTS",
    "TOPIC_AUDIT_EVENTS",
    "BaseEvent",
    "JournalPostedEvent",
    "StockMovementEvent",
    "MachineFaultEvent",
]
