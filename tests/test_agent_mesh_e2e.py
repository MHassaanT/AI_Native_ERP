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


@pytest.mark.asyncio
async def test_agents_api_dags_and_dispatch():
    """Verifies that the /agents/dags endpoints return populated DAGs and execute asynchronously."""
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from erp.api.app import create_app

    app = create_app()
    slug = f"mesh-{uuid.uuid4().hex[:6]}"
    email = f"mesh-admin@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Mesh Aerospace Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordMesh123!",
                "full_name": "Mesh Director",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Fetch latest (should auto-seed default baseline DAG if empty)
        latest_res = await client.get("/api/v1/agents/dags/latest", headers=headers)
        assert latest_res.status_code == 200, latest_res.text
        dag_data = latest_res.json()
        assert "dag_id" in dag_data
        assert "nodes" in dag_data
        assert len(dag_data["nodes"]) >= 4

        # 2. Dispatch a new custom RFQ DAG
        dispatch_res = await client.post(
            "/api/v1/agents/dispatch-rfq",
            json={
                "customer_name": "Rolls-Royce Aerospace",
                "inquiry_text": "Requesting 250 units titanium housing for Trent 1000 engine.",
                "target_sku": "FG-ENCLOSURE-IP67",
                "quantity": 250.0,
            },
            headers=headers,
        )
        assert dispatch_res.status_code == 200, dispatch_res.text
        new_dag = dispatch_res.json()
        assert new_dag["customer_name"] == "Rolls-Royce Aerospace"
        dag_id = new_dag["dag_id"]

        # Wait briefly for async execution across agents
        await asyncio.sleep(1.5)

        # 3. Fetch specific DAG by ID
        get_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert get_res.status_code == 200, get_res.text
        fetched = get_res.json()
        assert fetched["dag_id"] == dag_id
        assert fetched["status"] == "COMPLETED"
        # Verify node output results are populated
        revenue_node = next(n for n in fetched["nodes"] if n["name"] == "Parse RFQ Document")
        assert revenue_node["status"] == "COMPLETED"
        assert revenue_node["output_result"] is not None
        assert revenue_node["output_result"]["customer_name"] == "Rolls-Royce Aerospace"

        # 4. List all DAGs
        list_res = await client.get("/api/v1/agents/dags", headers=headers)
        assert list_res.status_code == 200, list_res.text
        all_dags = list_res.json()
        assert len(all_dags) >= 1
        assert any(d["dag_id"] == dag_id for d in all_dags)

