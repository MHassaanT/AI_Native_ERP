"""Tenant-scoped workflow inspection and recovery endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from erp.api.deps import DbSessionDep, TenantIdDep, require_roles
from erp.db.models.orchestration import DAGExecutionRecord
from erp.db.models.user import User
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.persistence import DAGRecoveryConflict, claim_dag_recovery
from erp.orchestration.worker import dag_executor

router = APIRouter(prefix="/workflows", tags=["Workflow Runs"])


class WorkflowRecoveryRequest(BaseModel):
    notes: str = Field(..., min_length=10, max_length=500)


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    visible_output_keys = {
        "invoice_number",
        "delivery_note_number",
        "invoice_amount",
        "general_ledger_status",
        "fulfillment_status",
        "gl_posted",
        "status",
        "compliance_verification",
    }
    output = node.get("output_result") or {}
    return {
        "task_id": node.get("task_id"),
        "name": node.get("name"),
        "agent_id": node.get("agent_id"),
        "status": node.get("status"),
        "started_at": node.get("started_at"),
        "completed_at": node.get("completed_at"),
        "error_message": node.get("error_message"),
        "result": {key: value for key, value in output.items() if key in visible_output_keys},
    }


def _workflow_response(record: DAGExecutionRecord) -> dict[str, Any]:
    return {
        "dag_id": record.dag_id,
        "status": record.status,
        "workflow_version": record.workflow_version,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "recovery_reason": record.recovery_reason,
        "recovery_requested_by": (
            str(record.recovery_requested_by) if record.recovery_requested_by else None
        ),
        "recovery_notes": record.recovery_notes,
        "nodes": [_node_summary(node) for node in record.workflow_state.get("nodes", [])],
    }


@router.get("")
async def list_workflows(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    records = (
        await session.execute(
            select(DAGExecutionRecord)
            .where(DAGExecutionRecord.tenant_id == tenant_id)
            .order_by(desc(DAGExecutionRecord.updated_at))
            .limit(limit)
        )
    ).scalars().all()
    return [_workflow_response(record) for record in records]


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> dict[str, Any]:
    record = (
        await session.execute(
            select(DAGExecutionRecord).where(
                DAGExecutionRecord.dag_id == workflow_id,
                DAGExecutionRecord.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return _workflow_response(record)


@router.post("/{workflow_id}/recover")
async def recover_workflow(
    workflow_id: str,
    request: WorkflowRecoveryRequest,
    tenant_id: TenantIdDep,
    reviewer: User = require_roles("FINANCE"),
) -> dict[str, Any]:
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    try:
        dag = await claim_dag_recovery(
            dag_id=workflow_id,
            tenant_id=tenant_id,
            reviewer_id=reviewer.user_id,
            notes=request.notes,
        )
    except DAGRecoveryConflict as exc:
        message = str(exc)
        raise HTTPException(
            status_code=404 if message == "Workflow not found." else 409,
            detail=message,
        ) from exc

    chief_orchestrator.active_dags[dag.dag_id] = dag
    await dag_executor.execute_dag(dag)
    held_nodes = [
        {"task_id": node.task_id, "name": node.name}
        for node in dag.nodes.values()
        if node.status.value == "PREEMPTED"
    ]
    return {
        "dag_id": dag.dag_id,
        "status": dag.to_dict()["status"],
        "held_nodes": held_nodes,
        "recovery_requested_by": str(reviewer.user_id),
        "recovery_notes": request.notes,
    }
