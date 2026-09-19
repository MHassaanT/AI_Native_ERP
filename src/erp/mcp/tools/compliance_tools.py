"""Compliance and Statutory MCP Tool Bindings."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.orchestration.guardrails import compliance_guardrail
from erp.orchestration.state import AgentActionProposal


async def tool_evaluate_statutory_rules(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for verifying proposed agent actions against SOX, GAAP, and RBAC policies."""
    proposal = AgentActionProposal(
        task_id=arguments.get("task_id", "task_mcp_eval"),
        agent_id=arguments["agent_id"],
        tenant_id=tenant_id,
        policy_class=arguments.get("policy_class", "STATUTORY_LEGAL"),
        resource_keys=arguments.get("resource_keys", []),
        state_mutation=arguments.get("state_mutation", {}),
    )
    res = compliance_guardrail.evaluate_action_proposal(
        proposal=proposal,
        action_name=arguments["action_name"],
    )
    return res.model_dump(mode="json")
