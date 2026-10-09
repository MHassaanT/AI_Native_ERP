"""Tests for WhatsApp support agent tool exposure and OTP handling primitives."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from erp.ai.whatsapp_support_agent import (
    DEFAULT_TOOLS,
    TOOL_DEFINITIONS,
    _configured_tools,
    _normalize_phone,
    _otp_digest,
)
from erp.api.routes.whatsapp import _require_internal_token
from erp.config import settings


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
