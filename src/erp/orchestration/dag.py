"""Hierarchical Directed Acyclic Graph (DAG) Task Engine."""

import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PREEMPTED = "PREEMPTED"


class TaskNode(BaseModel):
    """Represents an atomic subtask node within an enterprise execution DAG."""

    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    agent_id: str
    dependencies: set[str] = Field(default_factory=set)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_result: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class TaskDAG:
    """Manages DAG formation, cycle validation, and topological execution."""

    def __init__(
        self,
        dag_id: str | None = None,
        tenant_id: str | None = None,
        customer_name: str | None = None,
        inquiry_text: str | None = None,
    ):
        self.dag_id = dag_id or f"dag_{uuid.uuid4().hex[:8]}"
        self.tenant_id = str(tenant_id) if tenant_id else None
        self.customer_name = customer_name or "Enterprise Customer"
        self.inquiry_text = inquiry_text or ""
        self.created_at = datetime.now(UTC)
        self.nodes: dict[str, TaskNode] = {}

    def to_dict(self) -> dict[str, Any]:
        """Serializes DAG with node dependencies, statuses, and execution metadata."""
        node_list = []
        for n in self.nodes.values():
            n_dict = n.model_dump(mode="json")
            n_dict["dependencies"] = list(n.dependencies)
            node_list.append(n_dict)

        status = "COMPLETED" if self.is_finished() else "RUNNING"
        if all(n.status == TaskStatus.PENDING for n in self.nodes.values()):
            status = "DISPATCHED"

        return {
            "dag_id": self.dag_id,
            "tenant_id": self.tenant_id,
            "customer_name": self.customer_name,
            "inquiry_text": self.inquiry_text,
            "created_at": self.created_at.isoformat(),
            "status": status,
            "nodes": node_list,
        }

    def add_node(
        self,
        name: str,
        agent_id: str,
        dependencies: list[str] | None = None,
        input_payload: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> TaskNode:
        """Adds a task node to the DAG."""
        node_id = task_id or f"task_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"
        node = TaskNode(
            task_id=node_id,
            name=name,
            agent_id=agent_id,
            dependencies=set(dependencies or []),
            input_payload=input_payload or {},
        )
        self.nodes[node_id] = node
        self.validate()
        return node

    def validate(self) -> None:
        """Validates that graph is acyclic and dependencies exist."""
        # Verify dependency nodes exist
        for node in self.nodes.values():
            for dep_id in node.dependencies:
                if dep_id not in self.nodes:
                    raise ValueError(f"Task '{node.task_id}' depends on missing task '{dep_id}'")

        # Kahn's algorithm for cycle detection
        in_degree = {nid: len(n.dependencies) for nid, n in self.nodes.items()}
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        # Build adjacency list: dep -> dependents
        adj = defaultdict(list)
        for nid, node in self.nodes.items():
            for dep_id in node.dependencies:
                adj[dep_id].append(nid)

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(self.nodes):
            raise ValueError(f"Cycle detected in execution DAG '{self.dag_id}'")

    def get_ready_tasks(self) -> list[TaskNode]:
        """Returns all tasks whose dependencies have successfully completed."""
        ready = []
        for node in self.nodes.values():
            if node.status == TaskStatus.PENDING:
                all_deps_done = all(
                    self.nodes[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in node.dependencies
                )
                if all_deps_done:
                    node.status = TaskStatus.READY
                    ready.append(node)
        return ready

    def mark_completed(self, task_id: str, result: dict[str, Any]) -> None:
        """Marks a task node as completed."""
        node = self.nodes[task_id]
        node.status = TaskStatus.COMPLETED
        node.output_result = result
        node.completed_at = datetime.now(UTC)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Marks a task node as failed."""
        node = self.nodes[task_id]
        node.status = TaskStatus.FAILED
        node.error_message = error
        node.completed_at = datetime.now(UTC)

    def is_finished(self) -> bool:
        """Checks if all nodes are completed or failed."""
        return all(
            n.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PREEMPTED)
            for n in self.nodes.values()
        )
