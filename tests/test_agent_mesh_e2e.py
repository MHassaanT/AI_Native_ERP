"""Tests for deterministic commercial workflow coordination."""

import uuid
from decimal import Decimal

import pytest

from erp.mesh.agent_mesh import EnterpriseAgentMesh
from erp.mesh.tracer import TraceContext


@pytest.mark.asyncio
async def test_mesh_executes_inbound_rfq_workflow():
    mesh = EnterpriseAgentMesh()
    tenant_id = uuid.uuid4()

    summary = await mesh.execute_inbound_rfq_mesh_pipeline(
        tenant_id=tenant_id,
        customer_name="Boeing Defense",
        target_sku="AERO-TITANIUM-RIB",
        quantity=Decimal("150.00"),
        delivery_deadline_days=21,
    )

    assert summary.status == "COMPLETED"
    assert summary.is_compliance_verified is True
    assert summary.tasks_dispatched >= 4
    assert summary.tasks_completed == summary.tasks_dispatched
    assert "CHIEF_ORCHESTRATOR" in summary.participating_agents
    assert "REVENUE" in summary.participating_agents
    assert "SUPPLY_CHAIN" in summary.participating_agents
    assert "PRODUCTION" in summary.participating_agents
    assert "COMPLIANCE" in summary.participating_agents

    output = summary.output_summary
    assert output["customer_name"] == "Boeing Defense"
    assert output["sku"] == "AERO-TITANIUM-RIB"
    assert output["quantity"] == 150.0
    assert output["makespan_minutes"] >= 0
    assert output["guaranteed_margin"] >= 22.0
    assert "compliance_token" in output


def test_mesh_tracer_child_span_generation():
    root_tracer = TraceContext()
    assert root_tracer.trace_id.startswith("trace_")
    assert root_tracer.parent_span_id is None

    child = root_tracer.create_child_span(subagent_name="PRODUCTION_SCHEDULER")
    assert child.trace_id == root_tracer.trace_id
    assert child.parent_span_id == root_tracer.span_id
    assert child.service_name == "PRODUCTION_SCHEDULER"
    assert child.span_id != root_tracer.span_id


def test_retired_agent_routes_are_not_registered_and_workflows_remain():
    from erp.api.app import create_app
    from erp.db.models import Base
    from erp.mcp.server import AVAILABLE_TOOLS

    app = create_app()
    paths = app.openapi()["paths"]

    assert "/api/v1/workflows" in paths
    assert "/api/v1/workflows/{workflow_id}" in paths
    assert "/api/v1/workflows/{workflow_id}/recover" in paths
    assert not any(path.startswith("/api/v1/agents") for path in paths)
    assert not any(path.startswith("/api/v1/approvals") for path in paths)
    assert not {
        "agent_definitions",
        "agent_execution_runs",
        "agent_step_logs",
        "agent_approvals",
        "agent_communications",
    } & Base.metadata.tables.keys()
    assert not {
        "execute_shift_trade",
        "authorize_expense_payout",
    } & {tool.name for tool in AVAILABLE_TOOLS}
