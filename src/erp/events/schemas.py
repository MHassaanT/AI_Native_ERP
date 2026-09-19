"""Domain Event Pydantic Schemas for type-safe event serialization."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base schema for all domain events emitted to the streaming substrate."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    payload: dict[str, Any] = Field(default_factory=dict)


class JournalPostedEvent(BaseEvent):
    """Emitted when a balanced journal voucher passes ledger validation and commits."""

    event_type: str = "erp.finance.journal_posted"
    transaction_id: uuid.UUID
    posting_date: str
    total_volume: Decimal
    tier: str


class StockMovementEvent(BaseEvent):
    """Emitted when inventory is received, transferred, or consumed."""

    event_type: str = "erp.inventory.stock_level_changed"
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    actual_qty: Decimal
    new_qty: Decimal


class MachineFaultEvent(BaseEvent):
    """Emitted by IoT edge gateway or sensor anomaly engine."""

    event_type: str = "erp.production.machine_fault"
    workstation_id: uuid.UUID
    severity: str  # WARNING, CRITICAL_FAULT
    vibration_rms: float | None = None
    temperature_celsius: float | None = None
