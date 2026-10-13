"""Tests for WhatsApp support agent tool exposure and OTP handling primitives."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from erp.ai.whatsapp_support_agent import (
    DEFAULT_TOOLS,
    TOOL_DEFINITIONS,
    WhatsAppAgentProviderError,
    _configured_tools,
    _normalize_phone,
    _otp_digest,
)
from erp.api.routes import whatsapp as whatsapp_routes
from erp.api.routes.whatsapp import (
    WhatsAppInboundRequest,
    _oauth_frontend_origin,
    _require_internal_token,
    process_whatsapp_inbound,
)
from erp.config import settings
from erp.db.models.whatsapp import WhatsAppConversation, WhatsAppMessage


def test_support_tools_default_to_registered_support_actions():
    assert _configured_tools([]) == list(DEFAULT_TOOLS)
    assert "escalate_to_human" in TOOL_DEFINITIONS
    assert "transfer_to_coding_agent" not in TOOL_DEFINITIONS


def test_tenant_bindings_only_expose_enabled_tools():
    bindings = [
        SimpleNamespace(tool_name="create_support_issue", is_enabled=True),
        SimpleNamespace(tool_name="get_my_appointments", is_enabled=False),
        SimpleNamespace(tool_name="not_a_registered_tool", is_enabled=True),
    ]
    assert _configured_tools(bindings) == ["create_support_issue"]


def test_otp_digest_is_bound_to_tenant_conversation_and_lead():
    digest = _otp_digest("tenant-a", "conversation-a", "lead-a", "123456")
    assert digest == _otp_digest("tenant-a", "conversation-a", "lead-a", "123456")
    assert digest != _otp_digest("tenant-b", "conversation-a", "lead-a", "123456")
    assert digest != _otp_digest("tenant-a", "conversation-b", "lead-a", "123456")
    assert digest != _otp_digest("tenant-a", "conversation-a", "lead-a", "654321")


def test_phone_normalization_removes_formatting_only():
    assert _normalize_phone("+1 (415) 555-0123") == "14155550123"


@pytest.mark.asyncio
async def test_internal_whatsapp_endpoint_requires_shared_token(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_INTERNAL_TOKEN", "a-long-internal-test-token")
    with pytest.raises(HTTPException) as exc:
        await _require_internal_token("wrong-token")
    assert exc.value.status_code == 401

    await _require_internal_token("a-long-internal-test-token")


def test_airtable_oauth_origin_uses_allowlisted_referer_when_origin_is_missing():
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"referer", b"https://erp.example.com/whatsapp"),
            ],
        }
    )

    assert _oauth_frontend_origin(request, {"https://erp.example.com"}) == "https://erp.example.com"


def test_airtable_oauth_rejects_unapproved_origin_without_referer_fallback():
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"origin", b"https://untrusted.example.com"),
                (b"referer", b"https://erp.example.com/whatsapp"),
            ],
        }
    )

    assert _oauth_frontend_origin(request, {"https://erp.example.com"}) is None


@pytest.mark.asyncio
async def test_llm_failure_persists_inbound_and_fallback_reply(monkeypatch, tenant_id):
    conversation = WhatsAppConversation(
        conversation_id=uuid.uuid4(),
        tenant_id=tenant_id,
        phone_number="14155550123",
        status="ACTIVE",
    )

    class Result:
        def __init__(self, one=None, many=None):
            self.one = one
            self.many = many or []

        def scalar_one(self):
            return self.one

        def scalar_one_or_none(self):
            return self.one

        def scalars(self):
            return self

        def all(self):
            return self.many

    class FakeSession:
        def __init__(self):
            self.execute_results = iter(
                [Result(), Result(one=conversation), Result(), Result(many=[])]
            )
            self.added = []

        async def execute(self, _statement):
            return next(self.execute_results)

        def add(self, instance):
            if isinstance(instance, WhatsAppMessage) and instance.message_id is None:
                instance.message_id = uuid.uuid4()
            self.added.append(instance)

        async def flush(self):
            return None

    async def fail_support_turn(**_kwargs):
        raise WhatsAppAgentProviderError("LLM provider request failed (ReadTimeout).")

    monkeypatch.setattr(whatsapp_routes, "run_whatsapp_support_turn", fail_support_turn)
    session = FakeSession()
    response = await process_whatsapp_inbound(
        WhatsAppInboundRequest(
            tenant_id=tenant_id,
            provider_message_id="wamid-inbound-timeout",
            phone_number="14155550123",
            text="What is the latest update?",
        ),
        session,
    )

    inbound, outbound = session.added
    assert inbound.direction == "INBOUND"
    assert inbound.content == "What is the latest update?"
    assert outbound.direction == "OUTBOUND"
    assert outbound.content == response["answer"]
    assert outbound.metadata_json["reply_to_provider_message_id"] == "wamid-inbound-timeout"
    assert response["should_send"] is True
    assert response["answer"] == whatsapp_routes.SUPPORT_UNAVAILABLE_REPLY
