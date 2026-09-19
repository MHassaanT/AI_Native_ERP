"""Topic definitions and topography for Redpanda / Kafka streaming (PRD §Event Streaming)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicConfig:
    name: str
    partitions: int
    replication_factor: int
    retention_days: int
    key_pattern: str
    description: str


TOPIC_FINANCE_JOURNAL_EVENTS = TopicConfig(
    name="erp.finance.journal_events",
    partitions=16,
    replication_factor=3,
    retention_days=2555,  # 7 Years
    key_pattern="{tenant_id}:{account_code}",
    description="General Ledger journal mutations and clearing events",
)

TOPIC_SUPPLY_CHAIN_EVENTS = TopicConfig(
    name="erp.supplychain.events",
    partitions=32,
    replication_factor=3,
    retention_days=90,
    key_pattern="{tenant_id}:{warehouse_id}",
    description="Stock movement, dynamic ROP, purchase orders, goods receipts",
)

TOPIC_PRODUCTION_TELEMETRY = TopicConfig(
    name="erp.production.telemetry",
    partitions=64,
    replication_factor=3,
    retention_days=14,
    key_pattern="{tenant_id}:{workstation_id}",
    description="IoT vibration, temperature, machine faults, work order status",
)

TOPIC_WORKFORCE_EVENTS = TopicConfig(
    name="erp.workforce.events",
    partitions=16,
    replication_factor=3,
    retention_days=365,
    key_pattern="{tenant_id}:{employee_id}",
    description="Shift swaps, roster adjustments, expense claim submissions",
)

TOPIC_CRM_EVENTS = TopicConfig(
    name="erp.crm.events",
    partitions=16,
    replication_factor=3,
    retention_days=365,
    key_pattern="{tenant_id}:{customer_id}",
    description="Inbound RFQs, sales orders, quote accepted",
)

TOPIC_AUDIT_EVENTS = TopicConfig(
    name="erp.audit.events",
    partitions=16,
    replication_factor=3,
    retention_days=2555,  # 7 Years
    key_pattern="{tenant_id}:{agent_id}",
    description="Cryptographic agent audit events and verification alerts",
)

ALL_TOPICS = [
    TOPIC_FINANCE_JOURNAL_EVENTS,
    TOPIC_SUPPLY_CHAIN_EVENTS,
    TOPIC_PRODUCTION_TELEMETRY,
    TOPIC_WORKFORCE_EVENTS,
    TOPIC_CRM_EVENTS,
    TOPIC_AUDIT_EVENTS,
]
