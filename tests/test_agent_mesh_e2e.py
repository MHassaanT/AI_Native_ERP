"""End-to-End Tests for 7-Agent Autonomous Mesh Execution Pipeline (PRD §Agent Mesh)."""

import uuid
from decimal import Decimal

import pytest

from erp.mesh.agent_mesh import EnterpriseAgentMesh
from erp.mesh.tracer import TraceContext


@pytest.mark.asyncio
async def test_agent_mesh_executes_inbound_rfq_pipeline():
    """Verifies that the full 7-agent mesh executes the RFQ workflow across multiple domain agents."""
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

    # Verify output metrics
    out = summary.output_summary
    assert out["customer_name"] == "Boeing Defense"
    assert out["sku"] == "AERO-TITANIUM-RIB"
    assert out["quantity"] == 150.0
    assert out["makespan_minutes"] >= 0
    assert out["guaranteed_margin"] >= 22.0
    assert "compliance_token" in out


def test_mesh_tracer_child_span_generation():
    """Verifies OpenTelemetry-style trace context propagation across agents."""
    root_tracer = TraceContext()
    assert root_tracer.trace_id.startswith("trace_")
    assert root_tracer.parent_span_id is None

    # Spawn child span for Production agent
    child = root_tracer.create_child_span(subagent_name="PRODUCTION_SCHEDULER")
    assert child.trace_id == root_tracer.trace_id
    assert child.parent_span_id == root_tracer.span_id
    assert child.service_name == "PRODUCTION_SCHEDULER"
    assert child.span_id != root_tracer.span_id
