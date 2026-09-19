"""Unit Tests for Model Context Protocol (MCP) JSON-RPC 2.0 Server."""

import uuid

import pytest

from erp.mcp.schemas import MCPRequest
from erp.mcp.server import mcp_server


class TestMCPServer:
    """Tests JSON-RPC 2.0 tool server protocol."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_tools(self):
        req = MCPRequest(id=1, method="tools/list")
        resp = await mcp_server.handle_request(
            request=req,
            session=None,  # Not needed for list
            tenant_id=uuid.uuid4(),
        )

        assert resp.id == 1
        assert resp.error is None
        assert "tools" in resp.result
        tool_names = {t["name"] for t in resp.result["tools"]}
        assert "stage_ledger_transaction" in tool_names
        assert "execute_three_way_match" in tool_names
        assert "reconcile_bank_transaction" in tool_names
        assert "evaluate_statutory_rules" in tool_names

    @pytest.mark.asyncio
    async def test_evaluate_statutory_rules_tool_call(self):
        req = MCPRequest(
            id=2,
            method="tools/call",
            params={
                "name": "evaluate_statutory_rules",
                "arguments": {
                    "agent_id": "FINANCIAL_CONTROLLER",
                    "action_name": "stage_ledger_transaction",
                    "state_mutation": {"total": 5000},
                },
            },
        )
        resp = await mcp_server.handle_request(
            request=req,
            session=None,
            tenant_id=uuid.uuid4(),
        )

        assert resp.id == 2
        assert resp.error is None
        assert resp.result["isError"] is False
        assert len(resp.result["content"]) == 1
        content_text = resp.result["content"][0]["text"]
        assert "'is_compliant': True" in content_text

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_jsonrpc_error(self):
        req = MCPRequest(
            id=3,
            method="tools/call",
            params={"name": "non_existent_tool", "arguments": {}},
        )
        resp = await mcp_server.handle_request(
            request=req,
            session=None,
            tenant_id=uuid.uuid4(),
        )

        assert resp.id == 3
        assert resp.error is not None
        assert resp.error["code"] == -32601

    @pytest.mark.asyncio
    async def test_invalid_method_returns_error(self):
        req = MCPRequest(id=4, method="invalid/method")
        resp = await mcp_server.handle_request(
            request=req,
            session=None,
            tenant_id=uuid.uuid4(),
        )

        assert resp.id == 4
        assert resp.error is not None
        assert resp.error["code"] == -32600
