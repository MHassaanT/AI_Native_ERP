"""Comprehensive Automated Test Suite for Autonomous AI Workforce & HITL Governance."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from erp.api.app import app
from erp.auth.security import create_access_token
from erp.agents.core.approval_engine import approval_engine
from erp.agents.core.llm_gateway import llm_gateway
from erp.agents.core.orchestrator import orchestrator
from erp.agents.supervisors.finance_compliance_agent import finance_compliance_agent
from erp.agents.supervisors.hr_workforce_agent import hr_workforce_agent
from erp.agents.supervisors.inventory_controller import inventory_controller
from erp.agents.supervisors.mes_quality_supervisor import mes_quality_supervisor
from erp.agents.supervisors.procurement_supervisor import procurement_supervisor
from erp.agents.supervisors.sales_sdr_agent import sales_sdr_agent
from erp.db.models.agents import (
    AgentApproval,
    AgentCommunication,
    AgentDefinition,
    AgentExecutionRun,
    ApprovalStatus,
    RiskLevel,
)
from erp.db.models.crm import Lead
from erp.db.models.inventory import Batch, Item, StockLevel, Warehouse
from erp.db.models.purchasing import PurchaseOrder, Supplier
from erp.db.models.sales import Customer, SalesInvoice
from erp.db.session import async_session_factory

DEFAULT_TENANT_ID = uuid.UUID("308b946e-0a85-4ffa-a235-2706632aadd2")


@pytest.mark.asyncio
async def test_llm_gateway_structured_json():
    """Verifies that Google Gemini generates valid structured JSON for reasoning."""
    res = await llm_gateway.ainvoke_json(
        prompt="Analyze a component requirement of 25 units. Estimate unit cost and lead time in days. Return JSON with 'unit_cost' (float) and 'lead_time_days' (int).",
        system_prompt="You are an enterprise AI."
    )
    assert isinstance(res, dict)
    assert "unit_cost" in res or "lead_time_days" in res


@pytest.mark.asyncio
async def test_procurement_supervisor_and_hitl_approval():
    """Tests end-to-end autonomous procurement cycle and HITL approval execution."""
    async with async_session_factory() as session:
        wh = Warehouse(
            warehouse_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            warehouse_code=f"WH-AUTO-{uuid.uuid4().hex[:6]}",
            warehouse_name="Autonomous Procurement Test WH",
        )
        supplier = Supplier(
            supplier_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            supplier_code=f"SUP-AUTO-{uuid.uuid4().hex[:6]}",
            supplier_name="Global Steel Dynamics",
            otif_score=Decimal("92.50"),
        )
        item = Item(
            item_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            item_code=f"RAW-STL-{uuid.uuid4().hex[:6]}",
            item_name="Precision Cold-Rolled Steel Rods",
            standard_rate=Decimal("45.00"),
            reorder_level=Decimal("50.00"),
        )
        stock = StockLevel(
            stock_level_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            item_id=item.item_id,
            warehouse_id=wh.warehouse_id,
            current_qty=Decimal("20.00"),  # Below ROP of 50.0!
        )
        session.add_all([wh, supplier, item, stock])
        await session.commit()

    run = await procurement_supervisor.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "AWAITING_APPROVAL"
    assert "Procurement cycle initiated" in run.summary

    async with async_session_factory() as session:
        res = await session.execute(
            select(AgentApproval).where(
                AgentApproval.tenant_id == DEFAULT_TENANT_ID,
                AgentApproval.run_id == run.run_id,
                AgentApproval.action_type == "CREATE_PURCHASE_ORDER",
            )
        )
        approval = res.scalar_one_or_none()
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING
        assert approval.risk_level == RiskLevel.HIGH
        assert approval.required_role == "Finance"
        assert "items" in approval.action_payload

        # Test Manager Approval Execution
        resolved = await approval_engine.resolve_approval(
            approval_id=approval.approval_id,
            decision=ApprovalStatus.APPROVED,
            reviewer_notes="Approved by Finance Controller via test runner.",
        )
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.reviewed_at is not None

        # Verify PurchaseOrder was actually created in database
        selected_supplier_id = uuid.UUID(approval.action_payload["supplier_id"])
        po_res = await session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.tenant_id == DEFAULT_TENANT_ID,
                PurchaseOrder.supplier_id == selected_supplier_id,
            )
        )
        created_po = po_res.scalars().first()
        assert created_po is not None
        assert created_po.total_amount > Decimal("0")


@pytest.mark.asyncio
async def test_sales_sdr_agent_cycle():
    """Tests autonomous lead evaluation, Gemini ICP qualification, and WhatsApp pitch."""
    async with async_session_factory() as session:
        lead = Lead(
            lead_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            lead_name="Ahmad Hassan",
            company_name="Apex Logistics & Freight",
            email_id="ahmad@apexlogistics.com",
            phone="+923219876543",
            status="LEAD",
        )
        session.add(lead)
        await session.commit()

    run = await sales_sdr_agent.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "COMPLETED"
    assert "Evaluated lead" in run.summary

    async with async_session_factory() as session:
        res = await session.execute(select(Lead).where(Lead.lead_id == lead.lead_id))
        updated_lead = res.scalar_one()
        assert updated_lead.status in ["INTERESTED", "QUALIFICATION"]

        comm_res = await session.execute(
            select(AgentCommunication).where(
                AgentCommunication.tenant_id == DEFAULT_TENANT_ID,
                AgentCommunication.run_id == run.run_id,
            )
        )
        comm = comm_res.scalars().first()
        assert comm is not None
        assert comm.recipient == "+923219876543"


@pytest.mark.asyncio
async def test_inventory_controller_cycle():
    """Tests autonomous batch shelf-life audit and alert logging."""
    async with async_session_factory() as session:
        item = Item(
            item_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            item_code=f"ITM-EXP-{uuid.uuid4().hex[:6]}",
            item_name="Perishable Reagent Fluid",
        )
        session.add(item)
        await session.flush()

        batch = Batch(
            batch_id=uuid.uuid4(),
            batch_number=f"LOT-EXP-{uuid.uuid4().hex[:6]}",
            tenant_id=DEFAULT_TENANT_ID,
            item_id=item.item_id,
            expiry_date=datetime.now(timezone.utc).date() + timedelta(days=15),
        )
        session.add(batch)
        await session.commit()

    run = await inventory_controller.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "COMPLETED"


@pytest.mark.asyncio
async def test_hr_workforce_agent_cycle():
    """Tests autonomous HR audit, project pacing, and payroll pre-flight."""
    run = await hr_workforce_agent.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "COMPLETED"
    assert "Workforce audit completed" in run.summary


@pytest.mark.asyncio
async def test_mes_quality_supervisor_cycle():
    """Tests autonomous MES scheduling, IoT telemetry triage, and quality audit."""
    run = await mes_quality_supervisor.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "COMPLETED"
    assert "MES & Quality audit completed" in run.summary


@pytest.mark.asyncio
async def test_finance_compliance_agent_cycle():
    """Tests autonomous overdue AR scanning, tiered dunning, and budget sentinel."""
    async with async_session_factory() as session:
        cust = Customer(
            customer_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            customer_code=f"CUST-AUTO-{uuid.uuid4().hex[:6]}",
            customer_name="Overdue Corp International",
        )
        session.add(cust)
        await session.flush()

        inv = SalesInvoice(
            invoice_id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT_ID,
            customer_id=cust.customer_id,
            invoice_number=f"INV-OVERDUE-{uuid.uuid4().hex[:6]}",
            invoice_date=datetime.now(timezone.utc).date() - timedelta(days=45),
            due_date=datetime.now(timezone.utc).date() - timedelta(days=15),
            subtotal=Decimal("12500.00"),
            total_amount=Decimal("12500.00"),
            status="ISSUED",
        )
        session.add(inv)
        await session.commit()

    run = await finance_compliance_agent.execute_cycle(tenant_id=DEFAULT_TENANT_ID, trigger_type="MANUAL")
    assert run.status == "COMPLETED"
    assert "Finance & Compliance audit completed" in run.summary


@pytest.mark.asyncio
async def test_rest_api_agent_hub_and_approvals():
    """Tests the REST API endpoints for agent operations and HITL approvals."""
    token = create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(DEFAULT_TENANT_ID)})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. List Agents
        r1 = await ac.get("/api/v1/agents", headers=headers)
        assert r1.status_code == 200
        agents_data = r1.json()
        assert len(agents_data) >= 6
        slugs = [a["slug"] for a in agents_data]
        assert "procurement_supervisor" in slugs
        assert "sales_sdr_agent" in slugs

        # 2. List Approvals
        r2 = await ac.get("/api/v1/approvals", headers=headers)
        assert r2.status_code == 200

        # 3. List Communications
        r3 = await ac.get("/api/v1/agents/communications", headers=headers)
        assert r3.status_code == 200
        comms_data = r3.json()
        assert isinstance(comms_data, list)
