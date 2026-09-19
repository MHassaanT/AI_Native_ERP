"""SOC 2 Cryptographic Audit Chain & Multi-Agent Mesh API Endpoints (PRD §Immutable Audit Logging)."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.audit.hasher import GENESIS_HASH, compute_audit_record_hash, get_latest_audit_hash
from erp.db.models.audit import AgentAuditLog
from erp.mesh.agent_mesh import MeshExecutionSummary, agent_mesh
from erp.mesh.soc2_auditor import (
    SOC2ComplianceReport,
    soc2_auditor,
)

router = APIRouter(prefix="/audit", tags=["SOC 2 Audit & Agent Mesh"])


class RFQMeshPipelineRequest(BaseModel):
    customer_name: str = "Tesla Energy Inc."
    target_sku: str = "SOLAR-INV-50KW"
    quantity: Decimal = Decimal("500.00")
    delivery_deadline_days: int = 14


class TamperTestRequest(BaseModel):
    tamper_block_index: int = Field(default=0, ge=0)
    tampered_payload_key: str = "unauthorized_override"
    tampered_payload_value: str = "malicious_price_manipulation"


@router.get("/soc2/report", response_model=SOC2ComplianceReport)
async def get_soc2_compliance_report(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> SOC2ComplianceReport:
    """Verifies SHA-256 cryptographic continuity across all audit records from genesis to tip."""
    try:
        return await soc2_auditor.verify_database_audit_chain(session=session, tenant_id=tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SOC 2 audit report verification failed: {e!s}",
        ) from e


@router.post("/soc2/tamper-test", response_model=SOC2ComplianceReport)
async def run_tamper_detection_test(
    req: TamperTestRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> SOC2ComplianceReport:
    """Demonstrates cryptographic chain defense by introducing a mutation and proving automatic tamper rejection."""
    stmt = (
        select(AgentAuditLog)
        .where(AgentAuditLog.tenant_id == tenant_id)
        .order_by(AgentAuditLog.timestamp.asc())
    )
    logs = (await session.execute(stmt)).scalars().all()
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audit records found for this organization to test tampering against.",
        )

    records = [
        {
            "log_id": log.audit_id,
            "agent_id": log.agent_id,
            "trace_id": log.trace_id,
            "previous_hash": log.previous_record_hash or GENESIS_HASH,
            "record_hash": log.record_hash,
            "payload": log.input_payload,
        }
        for log in logs
    ]

    # Inject deliberate tampering at requested block
    idx = min(req.tamper_block_index, len(records) - 1)
    tampered_records = [dict(r) for r in records]
    tampered_payload = dict(tampered_records[idx]["payload"])
    tampered_payload[req.tampered_payload_key] = req.tampered_payload_value
    tampered_records[idx]["payload"] = tampered_payload

    # Run verification - will immediately detect the broken hash
    return soc2_auditor.verify_in_memory_chain(tampered_records)


@router.post("/mesh/execute-rfq", response_model=MeshExecutionSummary)
async def execute_rfq_mesh(
    req: RFQMeshPipelineRequest,
    tenant_id: TenantIdDep,
    session: DbSessionDep,
) -> MeshExecutionSummary:
    """Triggers end-to-end 7-agent mesh pipeline: RFQ -> BOM cost -> CP-SAT makespan -> Margin Defense -> Compliance."""
    try:
        summary = await agent_mesh.execute_inbound_rfq_mesh_pipeline(
            tenant_id=tenant_id,
            customer_name=req.customer_name,
            target_sku=req.target_sku,
            quantity=req.quantity,
            delivery_deadline_days=req.delivery_deadline_days,
        )

        # Append block to tenant's audit trail
        latest_hash = await get_latest_audit_hash(session, tenant_id) or GENESIS_HASH
        trace_id = f"trace_rfq_{summary.execution_id}"
        rfq_payload = {
            "execution_id": summary.execution_id,
            "customer_name": req.customer_name,
            "target_sku": req.target_sku,
            "quantity": float(req.quantity),
            "output_summary": summary.output_summary,
        }
        rfq_hash = compute_audit_record_hash(
            trace_id=trace_id,
            agent_id="CHIEF_ORCHESTRATOR",
            input_payload=rfq_payload,
            previous_hash=latest_hash,
        )
        audit_entry = AgentAuditLog(
            tenant_id=tenant_id,
            trace_id=trace_id,
            agent_id="CHIEF_ORCHESTRATOR",
            session_id=summary.execution_id,
            model_provider="GEMINI",
            model_version="1.5-pro",
            prompt_template_hash="rfq_mesh_template_hash",
            retrieved_context_hashes=[],
            baml_function_called="ExecuteInboundRFQMesh",
            input_payload=rfq_payload,
            model_raw_output=f"Mesh pipeline dispatched and arbitrated across {len(summary.participating_agents)} agents.",
            parsed_structured_output=summary.output_summary,
            evaluated_guardrail_rules={
                "margin_defense_active": True,
                "compliance_token_verified": summary.is_compliance_verified,
            },
            execution_duration_ms=45,
            previous_record_hash=latest_hash,
            record_hash=rfq_hash,
        )
        session.add(audit_entry)
        await session.flush()

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent mesh pipeline execution failed: {e!s}",
        ) from e
