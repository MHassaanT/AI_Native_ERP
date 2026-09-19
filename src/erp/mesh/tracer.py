"""Distributed Trace Context Propagator (PRD §Immutable Audit Logging)."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class TraceContext(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex}")
    span_id: str = Field(default_factory=lambda: f"span_{uuid.uuid4().hex[:16]}")
    parent_span_id: str | None = None
    service_name: str = "ai_erp_agent_mesh"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def create_child_span(self, subagent_name: str) -> "TraceContext":
        """Spawns a linked child span for a domain subagent execution."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=f"span_{uuid.uuid4().hex[:16]}",
            parent_span_id=self.span_id,
            service_name=subagent_name,
            timestamp=datetime.now(UTC),
        )


mesh_tracer = TraceContext()
