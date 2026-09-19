"""Integration and verification test suite for PRD alignment components."""

import asyncio
from decimal import Decimal
import os
import uuid
import pytest

from erp.config import settings
from erp.baml_client.client import baml_client
from erp.db.vector_search import vector_search_engine
from erp.events.email_gateway import SMTPEmailHandler, mailbox, SentEmailMessage
from erp.events.gmail_integration import gmail_service
from erp.events.producer import event_producer, make_partition_key, TOPIC_RFQ_INBOUND
from erp.events.consumer import EventConsumer
from erp.ledger.rust_bridge import validate_ledger_entry_invariants, evaluate_autonomy_tier, AutonomyTier
from erp.ledger.invariants import LedgerLineProposal
from erp.ledger.exceptions import ZeroSumViolation, SingleSidedViolation, NegativeAmountViolation
from erp.quality.defect_evaluator import EdgeQualityEvaluator
from erp.quality.plc_diverter import plc_diverter
from erp.quality.lot_quarantine import lot_quarantine_manager
from erp.iot.mqtt_bridge import iot_bridge


@pytest.mark.asyncio
async def test_baml_multimodal_rfq_parsing():
    """Verifies BAML RFQ parser extracts customer, SKU, qty, urgency."""
    sample_inquiry = "Need urgent quote for 450 units of FG-ENCLOSURE-IP67 by 2026-12-01. Please reply to rfq@siemens-energy.com ASAP."
    result = await baml_client.parse_rfq_document(sample_inquiry)
    assert result.customer_name == "Siemens Energy AG"
    assert result.customer_email == "rfq@siemens-energy.com"
    assert result.commercial_urgency == "EXPEDITED"
    assert len(result.line_items) > 0
    assert result.line_items[0].requested_sku == "FG-ENCLOSURE-IP67"
    assert result.line_items[0].quantity == Decimal("450")


@pytest.mark.asyncio
async def test_baml_multimodal_invoice_parsing():
    """Verifies BAML invoice parser extracts invoice numbers and total amounts."""
    sample_invoice = "COMMERCIAL INVOICE #INV-2026-8841 Tax ID: US-EIN-12-3456789 Subtotal $12,500.00 Total Amount: $12,500.00"
    result = await baml_client.extract_invoice_metadata(sample_invoice)
    assert "INV-2026-8841" in result.invoice_number
    assert result.total_amount == Decimal("12500.00")
    assert result.extraction_confidence >= 0.90


@pytest.mark.asyncio
async def test_email_gateway_and_gmail_sync():
    """Verifies official Google OAuth configuration check, credentials persistence, and zero-mock enforcement."""
    tenant_id = "00000000-0000-0000-0000-000000000001"

    # 1. Verify unconfigured state correctly reports not configured
    os.environ.pop("GOOGLE_CLIENT_ID", None)
    os.environ.pop("GOOGLE_CLIENT_SECRET", None)
    settings.GOOGLE_CLIENT_ID = None
    settings.GOOGLE_CLIENT_SECRET = None
    unconfigured_auth = gmail_service.get_authorization_url(tenant_id=tenant_id)
    assert unconfigured_auth["is_configured"] is False
    assert unconfigured_auth["authorization_url"] is None

    # 2. Configure credentials
    saved = gmail_service.save_credentials(
        client_id="1234567890-testclient.apps.googleusercontent.com",
        client_secret="GOCSPX-testclientsecret123",
    )
    assert saved["is_configured"] is True

    # 3. Verify official Google authorization URL generated
    auth_data = gmail_service.get_authorization_url(tenant_id=tenant_id)
    assert auth_data["is_configured"] is True
    assert "accounts.google.com/o/oauth2/v2/auth" in auth_data["authorization_url"]
    assert "1234567890-testclient.apps.googleusercontent.com" in auth_data["authorization_url"]

    # 4. Verify that fake/invalid authorization code fails with real Google error (NO mock fallback)
    with pytest.raises(ValueError) as excinfo:
        await gmail_service.exchange_code_for_tokens(
            tenant_id=tenant_id,
            code="invalid_test_auth_code",
            redirect_uri="http://localhost:3000/inbox",
        )
    assert "Google OAuth token exchange failed" in str(excinfo.value)
    assert gmail_service.get_connection(tenant_id).is_connected is False

    # 5. Clean up credentials
    os.environ.pop("GOOGLE_CLIENT_ID", None)
    os.environ.pop("GOOGLE_CLIENT_SECRET", None)
    settings.GOOGLE_CLIENT_ID = None
    settings.GOOGLE_CLIENT_SECRET = None
    gmail_service.save_credentials("", "")
    gmail_service.disconnect(tenant_id)
    assert len(mailbox.inbox) == 0


@pytest.mark.asyncio
async def test_event_streaming_and_idempotency():
    """Verifies partition keys and Redis/in-memory idempotency locks."""
    await event_producer.start()
    tenant_id = uuid.uuid4()
    key = make_partition_key(tenant_id, "rfq", "rfq_001")
    assert key == f"{tenant_id}:rfq:rfq_001"

    sent = await event_producer.send_event(
        topic=TOPIC_RFQ_INBOUND,
        key=key,
        value={"event_id": "evt_test_stream_01", "action": "INBOUND_RFQ"},
    )
    assert sent is True

    async def dummy(t, k, v):
        pass

    test_evt_id = f"evt_stream_test_{uuid.uuid4().hex}"
    consumer = EventConsumer([TOPIC_RFQ_INBOUND], "test_group", dummy)
    assert await consumer.is_duplicate(test_evt_id) is False
    assert await consumer.is_duplicate(test_evt_id) is True


@pytest.mark.asyncio
async def test_vector_search_engine_tenant_isolation():
    """Verifies high-dimensional HNSW vector search with multi-tenant isolation."""
    await vector_search_engine.ensure_collection()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    vec = [0.02] * 1536

    # Upsert for Tenant A
    await vector_search_engine.upsert_vector(
        point_id=str(uuid.uuid4()),
        tenant_id=tenant_a,
        entity_type="CONTRACT",
        entity_id=uuid.uuid4(),
        vector=vec,
        content="Confidential supply contract for Tenant A",
    )

    # Search as Tenant A -> should find document
    hits_a = await vector_search_engine.search_similar(tenant_id=tenant_a, query_vector=vec, limit=5)
    assert len(hits_a) >= 1
    assert "Tenant A" in hits_a[0]["content"]

    # Search as Tenant B -> strict isolation must return zero results
    hits_b = await vector_search_engine.search_similar(tenant_id=tenant_b, query_vector=vec, limit=5)
    assert len(hits_b) == 0


def test_rust_deterministic_ledger_invariants():
    """Verifies deterministic zero-sum balancing, single-sided constraints, and autonomy ceilings."""
    # Balanced entry
    lines = [
        LedgerLineProposal(account_code="1010", cost_center="CC-01", debit_amount=Decimal("2400.00"), credit_amount=Decimal("0.00")),
        LedgerLineProposal(account_code="2010", cost_center="CC-01", debit_amount=Decimal("0.00"), credit_amount=Decimal("2400.00")),
    ]
    volume = validate_ledger_entry_invariants(lines)
    assert volume == Decimal("2400.0000")
    assert evaluate_autonomy_tier(volume) == AutonomyTier.AUTONOMOUS

    # Tier 2
    assert evaluate_autonomy_tier(Decimal("18000.00")) == AutonomyTier.DUAL_SUPERVISOR

    # Tier 3
    assert evaluate_autonomy_tier(Decimal("35000.00")) == AutonomyTier.HUMAN_MANDATORY

    # Unbalanced entry raises ZeroSumViolation
    unbalanced = [
        LedgerLineProposal(account_code="1010", cost_center="CC-01", debit_amount=Decimal("100.00"), credit_amount=Decimal("0.00")),
        LedgerLineProposal(account_code="2010", cost_center="CC-01", debit_amount=Decimal("0.00"), credit_amount=Decimal("95.00")),
    ]
    with pytest.raises(ZeroSumViolation):
        validate_ledger_entry_invariants(unbalanced)

    # Single-sided violation
    two_sided = [
        LedgerLineProposal(account_code="1010", cost_center="CC-01", debit_amount=Decimal("100.00"), credit_amount=Decimal("100.00")),
    ]
    with pytest.raises(SingleSidedViolation):
        validate_ledger_entry_invariants(two_sided)


@pytest.mark.asyncio
async def test_edge_quality_and_plc_diverter_sla():
    """Verifies optical defect evaluation, sub-200ms PLC trip SLA, and lot quarantine."""
    # Low confidence does not trip
    c_low = EdgeQualityEvaluator.evaluate_inspection(
        inspection_id="insp_test_01",
        item_code="FG-ENCLOSURE-IP67",
        lot_number="LOT-SAFE-01",
        workstation_code="WS-LINE-01",
        defect_type="SURFACE_CRACK",
        confidence_score=0.85,
    )
    assert c_low.is_defective is True
    assert c_low.trigger_plc_scrap_trip is False

    # High confidence (>0.98) trips PLC scrap diverter
    c_high = EdgeQualityEvaluator.evaluate_inspection(
        inspection_id="insp_test_02",
        item_code="FG-ENCLOSURE-IP67",
        lot_number="LOT-DEFECT-02",
        workstation_code="WS-LINE-01",
        defect_type="SURFACE_CRACK",
        confidence_score=0.99,
    )
    assert c_high.trigger_plc_scrap_trip is True

    # Test hardware diverter actuation latency < 200ms
    trip_record = await plc_diverter.execute_scrap_trip("insp_test_02", "WS-LINE-01")
    assert trip_record.solenoid_energized is True
    assert trip_record.trip_latency_ms < 200.0
    assert trip_record.sla_met_sub_200ms is True

    # Test lot quarantine and release
    q_res = await lot_quarantine_manager.record_inspection_and_evaluate_quarantine(
        session=None,
        tenant_id=uuid.uuid4(),
        classification=c_high,
    )
    assert q_res.is_quarantined is True
    assert "LOT-DEFECT-02" in lot_quarantine_manager.quarantined_lots

    # Clean up released lot
    lot_quarantine_manager.quarantined_lots.discard("LOT-DEFECT-02")
