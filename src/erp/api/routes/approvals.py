"""API routes for Human-in-the-Loop (HITL) Governance Center."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.core.approval_engine import (
    ApprovalConflictError,
    ApprovalNotFoundError,
    approval_engine,
)
from erp.api.deps import CurrentUserDep, DbSessionDep, TenantIdDep
from erp.db.models.agents import AgentApproval, ApprovalStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["Human-in-the-Loop Approvals"])


class ApprovalDecisionPayload(BaseModel):
    notes: Optional[str] = None
    modified_payload: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_approvals(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
):
    """Lists pending and historical HITL approvals."""
    query = select(AgentApproval).where(AgentApproval.tenant_id == tenant_id)
    if status_filter:
        query = query.where(AgentApproval.status == ApprovalStatus(status_filter.upper()))
    query = query.order_by(desc(AgentApproval.created_at)).limit(limit)

    res = await session.execute(query)
    approvals = res.scalars().all()
    return [
        {
            "approval_id": str(a.approval_id),
            "run_id": str(a.run_id),
            "agent_name": a.agent_name,
            "domain": a.domain.value,
            "action_type": a.action_type,
            "action_payload": a.action_payload,
            "risk_level": a.risk_level.value,
            "required_role": a.required_role,
            "ai_rationale": a.ai_rationale,
            "status": a.status.value,
            "action_execution_status": a.action_execution_status,
            "action_execution_result": a.action_execution_result,
            "reviewed_by": str(a.reviewed_by) if a.reviewed_by else None,
            "reviewer_notes": a.reviewer_notes,
            "modified_payload": a.modified_payload,
            "created_at": a.created_at.isoformat(),
            "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        }
        for a in approvals
    ]


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionPayload,
    tenant_id: TenantIdDep,
    reviewer: CurrentUserDep,
):
    """Approves a pending request and executes the underlying domain workflow."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    try:
        approval = await approval_engine.resolve_approval(
            approval_id=approval_id,
            tenant_id=tenant_id,
            decision=ApprovalStatus.MODIFIED if payload.modified_payload is not None else ApprovalStatus.APPROVED,
            reviewer_id=reviewer.user_id,
            reviewer_role=reviewer.role,
            reviewer_notes=payload.notes,
            modified_payload=payload.modified_payload,
        )
        return {
            "status": approval.status.value,
            "approval_id": str(approval.approval_id),
            "action_status": approval.status.value,
            "action_execution_status": approval.action_execution_status,
            "execution_result": approval.action_execution_result,
            "message": f"Action '{approval.action_type}' approved and successfully executed.",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail="Approval not found.") from e
    except ApprovalConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("Approval execution failed")
        raise HTTPException(status_code=500, detail="Approval action could not be completed.") from e


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionPayload,
    tenant_id: TenantIdDep,
    reviewer: CurrentUserDep,
):
    """Rejects a pending request and records reason feedback."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    try:
        approval = await approval_engine.resolve_approval(
            approval_id=approval_id,
            tenant_id=tenant_id,
            decision=ApprovalStatus.REJECTED,
            reviewer_id=reviewer.user_id,
            reviewer_role=reviewer.role,
            reviewer_notes=payload.notes or "Rejected by reviewer.",
        )
        return {
            "status": "SUCCESS",
            "approval_id": str(approval.approval_id),
            "action_status": approval.status.value,
            "message": f"Action '{approval.action_type}' rejected.",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail="Approval not found.") from e
    except ApprovalConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("Approval rejection failed")
        raise HTTPException(status_code=500, detail="Approval could not be rejected.") from e
