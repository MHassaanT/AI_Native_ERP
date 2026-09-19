"""Agent Orchestration and DAG API Endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from erp.api.deps import TenantIdDep
from erp.orchestration.conflict_resolution import ArbitrationResult
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.state import AgentActionProposal

router = APIRouter(prefix="/agents", tags=["Agent Orchestration"])


class TriggerRFQWorkflowRequest(BaseModel):
    customer_name: str
    inquiry_text: str
    target_sku: str = "FG-ENCLOSURE-IP67"
    quantity: float = 500.0


class ArbitrateProposalsRequest(BaseModel):
    proposals: list[AgentActionProposal]


@router.get("/states", summary="Get live agent lifecycle states")
async def get_agent_states():
    """Returns the current execution state of all domain subagents in the multi-agent mesh."""
    return chief_orchestrator.agent_states


@router.post("/dispatch-rfq", summary="Dispatch an RFQ evaluation task DAG")
async def dispatch_rfq_workflow(
    req: TriggerRFQWorkflowRequest,
    tenant_id: TenantIdDep,
):
    """Instantiates a multi-task DAG for commercial inquiry parsing, costing, and makespan verification."""
    dag = chief_orchestrator.build_rfq_workflow_dag(
        tenant_id=tenant_id,
        rfq_payload=req.model_dump(),
    )
    return {
        "dag_id": dag.dag_id,
        "nodes": [n.model_dump() for n in dag.nodes.values()],
        "status": "DISPATCHED",
    }


@router.post(
    "/arbitrate",
    response_model=ArbitrationResult,
    summary="Arbitrate cross-functional agent collision",
)
async def arbitrate_agent_collision(
    req: ArbitrateProposalsRequest,
    tenant_id: TenantIdDep,
):
    """Executes deterministic mathematical conflict resolution over competing agent action proposals."""
    return chief_orchestrator.arbitrate_agent_proposals(req.proposals)
