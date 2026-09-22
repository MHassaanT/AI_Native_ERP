"""Chief Orchestrator Agent Runtime (PRD §Chief Orchestrator Agent)."""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from erp.orchestration.conflict_resolution import ArbitrationResult, conflict_engine
from erp.orchestration.dag import TaskDAG, TaskNode
from erp.orchestration.state import AgentActionProposal, AgentState, SubagentContext

logger = logging.getLogger(__name__)


class OrchestratorExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    event_type: str
    tenant_id: uuid.UUID
    dag_id: str
    total_tasks: int
    completed_tasks: int = 0
    arbitration: ArbitrationResult | None = None
    status: str = "INITIALIZED"


class ChiefOrchestrator:
    """Decomposes enterprise events into typed DAGs, spawns sandboxed subagents, and arbitrates collisions."""

    def __init__(self):
        self.active_dags: dict[str, TaskDAG] = {}
        self.agent_states: dict[str, AgentState] = {
            "FINANCIAL_CONTROLLER": AgentState.IDLE,
            "SUPPLY_CHAIN": AgentState.IDLE,
            "PRODUCTION": AgentState.IDLE,
            "REVENUE": AgentState.IDLE,
            "WORKFORCE": AgentState.IDLE,
            "COMPLIANCE": AgentState.IDLE,
        }

    def build_rfq_workflow_dag(
        self,
        tenant_id: uuid.UUID,
        rfq_payload: dict[str, Any],
    ) -> TaskDAG:
        """Constructs an asynchronous DAG for multi-line customer RFQ evaluation."""
        dag = TaskDAG(
            dag_id=f"dag_rfq_{uuid.uuid4().hex[:6]}",
            tenant_id=str(tenant_id),
            customer_name=rfq_payload.get("customer_name") or "Enterprise Customer",
            inquiry_text=rfq_payload.get("inquiry_text") or "",
        )

        # Subtask 1: Revenue Agent parses inquiry
        t1 = dag.add_node(
            name="Parse RFQ Document",
            agent_id="REVENUE",
            input_payload=rfq_payload,
        )

        # Subtask 2: Supply Chain Agent checks material lead times (depends on t1)
        t2 = dag.add_node(
            name="Calculate Landed Material Costs",
            agent_id="SUPPLY_CHAIN",
            dependencies=[t1.task_id],
            input_payload={"tenant_id": str(tenant_id)},
        )

        # Subtask 3: Production Agent checks machine makespan via OR-Tools (depends on t1)
        t3 = dag.add_node(
            name="Verify Production Makespan Capacity",
            agent_id="PRODUCTION",
            dependencies=[t1.task_id],
            input_payload={"tenant_id": str(tenant_id)},
        )

        # Subtask 4: Revenue Agent synthesizes final quote with margin defense (depends on t2, t3)
        dag.add_node(
            name="Generate Margin-Defended Quote",
            agent_id="REVENUE",
            dependencies=[t2.task_id, t3.task_id],
            input_payload={"margin_floor": 0.22},
        )

        self.active_dags[dag.dag_id] = dag
        return dag

    def get_dags(self, tenant_id: uuid.UUID | str | None = None) -> list[TaskDAG]:
        """Returns list of DAGs sorted newest first, filtered by tenant when available."""
        dags = list(self.active_dags.values())
        if tenant_id:
            tenant_str = str(tenant_id)
            filtered = [d for d in dags if d.tenant_id is None or d.tenant_id == tenant_str]
            if filtered:
                dags = filtered
        from datetime import datetime, UTC
        dags.sort(key=lambda d: getattr(d, "created_at", datetime.min.replace(tzinfo=UTC)), reverse=True)
        return dags

    def get_dag(self, dag_id: str) -> TaskDAG | None:
        """Retrieves a specific DAG by its ID."""
        return self.active_dags.get(dag_id)

    def create_subagent_context(
        self,
        task: TaskNode,
        tenant_id: uuid.UUID,
    ) -> SubagentContext:
        """Formulates minimal, typed context sandbox for subagent execution."""
        return SubagentContext(
            task_id=task.task_id,
            agent_id=task.agent_id,
            tenant_id=tenant_id,
            assigned_subtask=task.name,
            input_payload=task.input_payload,
            schema_fragments=[f"table_{task.agent_id.lower()}"],
            retrieved_vector_chunks=[],
            boundary_constraints=[],
        )

    def arbitrate_agent_proposals(
        self,
        proposals: list[AgentActionProposal],
    ) -> ArbitrationResult:
        """Invokes the mathematical conflict resolution engine on concurrent agent actions."""
        return conflict_engine.arbitrate(proposals)


chief_orchestrator = ChiefOrchestrator()
