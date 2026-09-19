"""Agent State Lifecycle and Sandboxed Context Boundaries."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentState(StrEnum):
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    KILLED = "KILLED"
    PREEMPTED = "PREEMPTED"


class SubagentContext(BaseModel):
    """Sandboxed context window allocated to an individual domain subagent.

    Prevents global prompt history leakage and runaway token bloat.
    """

    task_id: str
    agent_id: str
    tenant_id: uuid.UUID
    assigned_subtask: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    schema_fragments: list[str] = Field(default_factory=list)
    retrieved_vector_chunks: list[str] = Field(default_factory=list)
    boundary_constraints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentActionProposal(BaseModel):
    """Structured mutation proposal emitted by a domain subagent."""

    proposal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str
    agent_id: str
    tenant_id: uuid.UUID
    policy_class: str = Field(
        ...,
        description="STATUTORY_LEGAL, FINANCIAL_SOLVENCY, CONTRACTUAL_SLA, CAPACITY_THROUGHPUT, DISCRETIONARY_COST",
    )
    resource_keys: list[str] = Field(
        ...,
        description="Keys of enterprise shared resources accessed (e.g. 'workstation:WS-01', 'vendor:SUP-01')",
    )
    state_mutation: dict[str, Any] = Field(
        default_factory=dict,
        description="Delta state mutation proposed",
    )
    monetary_value: float = 0.0
    risk_score: float = Field(default=0.1, ge=0.0, le=1.0)
    audit_rationale: str = ""
