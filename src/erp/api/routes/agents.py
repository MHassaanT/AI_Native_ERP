import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from erp.api.deps import TenantIdDep
from erp.orchestration.conflict_resolution import ArbitrationResult
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.state import AgentActionProposal
from erp.orchestration.worker import dag_executor

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
    # Execute DAG concurrently across agents
    asyncio.create_task(dag_executor.execute_dag(dag))
    return dag.to_dict()


@router.get("/dags", summary="List task DAGs")
async def list_task_dags(tenant_id: TenantIdDep):
    """Returns all active and completed task DAGs, sorted newest first."""
    dags = chief_orchestrator.get_dags(tenant_id)
    return [d.to_dict() for d in dags]


@router.get("/dags/latest", summary="Get most recent task DAG")
async def get_latest_task_dag(tenant_id: TenantIdDep):
    """Returns the most recent task DAG for the tenant."""
    dags = chief_orchestrator.get_dags(tenant_id)
    if not dags:
        # If empty, spawn an initial baseline DAG so the visualizer never shows blank
        sample_dag = chief_orchestrator.build_rfq_workflow_dag(
            tenant_id=tenant_id,
            rfq_payload={
                "customer_name": "AeroDynamics GmbH",
                "inquiry_text": "Need 500 units IP67 industrial enclosures by Q4.",
                "target_sku": "FG-ENCLOSURE-IP67",
                "quantity": 500.0,
            },
        )
        asyncio.create_task(dag_executor.execute_dag(sample_dag))
        return sample_dag.to_dict()
    return dags[0].to_dict()


@router.get("/dags/{dag_id}", summary="Get task DAG by ID")
async def get_task_dag(dag_id: str, tenant_id: TenantIdDep):
    """Returns task DAG structure, current status, dependencies, and node output results."""
    dag = chief_orchestrator.get_dag(dag_id)
    if not dag:
        raise HTTPException(status_code=404, detail=f"Task DAG '{dag_id}' not found.")
    return dag.to_dict()


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
