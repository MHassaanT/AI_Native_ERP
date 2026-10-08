"""Database persistence and startup recovery for DAG executions."""

from copy import deepcopy
from datetime import UTC, datetime
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from erp.db.models.orchestration import DAGExecutionRecord
from erp.db.session import async_session_factory
from erp.orchestration.dag import TaskDAG, TaskStatus


SAFE_RECOVERY_NODES = {
    ("REVENUE", "parse rfq document"),
    ("REVENUE", "extract order & buyer entity"),
    ("REVENUE", "generate margin-defended quote"),
    ("SUPPLY_CHAIN", "calculate landed material costs"),
    ("SUPPLY_CHAIN", "check inventory & stock availability"),
    ("PRODUCTION", "verify production makespan capacity"),
    # This node serializes all DB effects in one transaction and reconciles committed output
    # before attempting a stock, invoice, or ledger write.
    ("FINANCIAL_CONTROLLER", "fulfill delivery & post invoice to ledger"),
}


class DAGRecoveryConflict(ValueError):
    """Raised when a DAG is not eligible for an authorized recovery attempt."""


def _workflow_status(snapshot: dict[str, Any]) -> str:
    statuses = [node.get("status") for node in snapshot.get("nodes", [])]
    if statuses and all(status == "COMPLETED" for status in statuses):
        return "COMPLETED"
    if statuses and all(status in {"COMPLETED", "FAILED", "PREEMPTED"} for status in statuses):
        return "FAILED"
    if all(status == "PENDING" for status in statuses):
        return "DISPATCHED"
    return "RUNNING"


async def persist_dag_snapshot(dag: Any) -> None:
    """Persist a complete, tenant-owned DAG snapshot before/after execution batches."""
    if not dag.tenant_id:
        raise ValueError("Cannot persist a DAG without an authoritative tenant_id.")
    tenant_id = uuid.UUID(dag.tenant_id)
    snapshot = dag.to_dict()
    status = _workflow_status(snapshot)
    snapshot["status"] = status
    values = {
        "dag_id": dag.dag_id,
        "tenant_id": tenant_id,
        "workflow_version": 1,
        "status": status,
        "workflow_state": snapshot,
        "recovery_reason": None,
    }
    async with async_session_factory() as session:
        statement = insert(DAGExecutionRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[DAGExecutionRecord.dag_id],
            set_={
                "tenant_id": statement.excluded.tenant_id,
                "status": statement.excluded.status,
                "workflow_state": statement.excluded.workflow_state,
                "recovery_reason": None,
                "updated_at": datetime.now(UTC),
            },
            where=DAGExecutionRecord.tenant_id == tenant_id,
        )
        result = await session.execute(statement)
        if result.rowcount != 1:
            raise RuntimeError("DAG identifier is already associated with a different tenant.")
        await session.commit()


async def list_tenant_dag_snapshots(tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return persisted workflow snapshots for exactly one tenant."""
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(DAGExecutionRecord.workflow_state)
                .where(DAGExecutionRecord.tenant_id == tenant_id)
                .order_by(DAGExecutionRecord.updated_at.desc())
            )
        ).scalars().all()
        return list(rows)


async def claim_dag_recovery(
    dag_id: str,
    tenant_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    notes: str,
) -> TaskDAG:
    """Claim a quarantined workflow and reset only explicitly safe nodes for retry."""
    async with async_session_factory() as session:
        record = (
            await session.execute(
                select(DAGExecutionRecord)
                .where(
                    DAGExecutionRecord.dag_id == dag_id,
                    DAGExecutionRecord.tenant_id == tenant_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not record:
            raise DAGRecoveryConflict("Workflow not found.")
        if record.status != "RECOVERY_REQUIRED":
            raise DAGRecoveryConflict(f"Workflow cannot be recovered from status {record.status}.")

        snapshot = deepcopy(record.workflow_state)
        try:
            snapshot_tenant_id = uuid.UUID(str(snapshot.get("tenant_id")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise DAGRecoveryConflict("Persisted workflow is missing a valid tenant identifier.") from exc
        if snapshot_tenant_id != tenant_id:
            raise DAGRecoveryConflict("Persisted workflow tenant does not match its owner record.")

        retry_count = 0
        for node in snapshot.get("nodes", []):
            key = (str(node.get("agent_id", "")).upper(), str(node.get("name", "")).lower())
            state = node.get("status")
            if key in SAFE_RECOVERY_NODES and state in {
                TaskStatus.PENDING.value,
                TaskStatus.PREEMPTED.value,
            }:
                retry_count += 1
                if state == TaskStatus.PREEMPTED.value:
                    node["status"] = TaskStatus.PENDING.value
                    node["error_message"] = None
                    node["started_at"] = None
                    node["completed_at"] = None
                    node["output_result"] = None
                    node["guardrail_evidence"] = None
            elif state == TaskStatus.PENDING.value:
                node["status"] = TaskStatus.PREEMPTED.value
                node["error_message"] = (
                    "Held during recovery because the node may repeat a non-idempotent side effect."
                )
                node["completed_at"] = datetime.now(UTC).isoformat()

        if retry_count == 0:
            raise DAGRecoveryConflict("Workflow has no interrupted nodes eligible for safe retry.")

        snapshot["status"] = "RECOVERING"
        snapshot["recovery_reason"] = "Authorized safe-node recovery requested."
        try:
            dag = TaskDAG.from_dict(snapshot)
        except (ValueError, TypeError, ValidationError, KeyError) as exc:
            raise DAGRecoveryConflict("Persisted workflow snapshot is invalid and cannot be recovered.") from exc
        record.status = "RECOVERING"
        record.workflow_state = snapshot
        record.recovery_reason = "Recovery was claimed; unsafe nodes remain held."
        record.recovery_requested_by = reviewer_id
        record.recovery_notes = notes
        record.recovery_started_at = datetime.now(UTC)
        record.updated_at = datetime.now(UTC)
        await session.commit()
        return dag


async def mark_interrupted_dags_for_recovery() -> int:
    """Quarantine unfinished workflows at startup; never replay side effects blindly."""
    count = 0
    async with async_session_factory() as session:
        records = (
            await session.execute(
                select(DAGExecutionRecord)
                .where(DAGExecutionRecord.status.in_(("DISPATCHED", "RUNNING", "RECOVERING")))
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for record in records:
            snapshot = dict(record.workflow_state or {})
            for node in snapshot.get("nodes", []):
                if node.get("status") == "RUNNING":
                    node["status"] = "PREEMPTED"
                    node["error_message"] = "Interrupted by process shutdown; reconcile side effects before retry."
                    node["completed_at"] = datetime.now(UTC).isoformat()
            snapshot["status"] = "RECOVERY_REQUIRED"
            snapshot["recovery_reason"] = (
                "Execution was interrupted. Reconcile database and external side effects before replay."
            )
            record.workflow_state = snapshot
            record.status = "RECOVERY_REQUIRED"
            record.recovery_reason = snapshot["recovery_reason"]
            record.updated_at = datetime.now(UTC)
            count += 1
        await session.commit()
    return count
