"""Unit Tests for Transactional Outbox serialization and schemas."""

import uuid
from decimal import Decimal

from erp.events.schemas import JournalPostedEvent, MachineFaultEvent, StockMovementEvent


class TestEventSchemas:
    """Tests Pydantic domain event schemas for outbox serialization."""

    def test_journal_posted_event_serialization(self):
        event = JournalPostedEvent(
            tenant_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            posting_date="2026-11-04",
            total_volume=Decimal("18450.0000"),
            tier="TIER_2",
        )
        data = event.model_dump(mode="json")
        assert data["event_type"] == "erp.finance.journal_posted"
        assert data["total_volume"] == "18450.0000"
        assert data["tier"] == "TIER_2"

    def test_stock_movement_event_serialization(self):
        item_id = uuid.uuid4()
        warehouse_id = uuid.uuid4()
        event = StockMovementEvent(
            tenant_id=uuid.uuid4(),
            item_id=item_id,
            warehouse_id=warehouse_id,
            actual_qty=Decimal("50.0000"),
            new_qty=Decimal("150.0000"),
        )
        data = event.model_dump(mode="json")
        assert data["event_type"] == "erp.inventory.stock_level_changed"
        assert data["actual_qty"] == "50.0000"

    def test_machine_fault_event_serialization(self):
        ws_id = uuid.uuid4()
        event = MachineFaultEvent(
            tenant_id=uuid.uuid4(),
            workstation_id=ws_id,
            severity="CRITICAL_FAULT",
            vibration_rms=5.2,
            temperature_celsius=88.5,
        )
        data = event.model_dump(mode="json")
        assert data["event_type"] == "erp.production.machine_fault"
        assert data["severity"] == "CRITICAL_FAULT"
        assert data["vibration_rms"] == 5.2
