"""API routes for Autonomous Agent Operations Hub."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.core.orchestrator import orchestrator
from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.agents import (
    AgentCommunication,
    AgentDefinition,
    AgentExecutionRun,
    AgentStepLog,
    AutonomyLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Autonomous Agents"])


class AgentConfigUpdate(BaseModel):
    autonomy_level: Optional[AutonomyLevel] = None
    interval_seconds: Optional[int] = None
    is_active: Optional[bool] = None
    system_prompt: Optional[str] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_agents(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Lists all registered autonomous supervisors and their current status."""
    res = await session.execute(
        select(AgentDefinition).where(AgentDefinition.tenant_id == tenant_id)
    )
    agents = res.scalars().all()
    result = []
    for agent in agents:
        # Get last execution run
        run_res = await session.execute(
            select(AgentExecutionRun)
            .where(AgentExecutionRun.agent_id == agent.agent_id)
            .order_by(desc(AgentExecutionRun.started_at))
            .limit(1)
        )
        last_run = run_res.scalar_one_or_none()

        result.append({
            "agent_id": str(agent.agent_id),
            "name": agent.name,
            "slug": agent.slug,
            "domain": agent.domain.value,
            "description": agent.description,
            "autonomy_level": agent.autonomy_level.value,
            "trigger_type": agent.trigger_type,
            "interval_seconds": agent.interval_seconds,
            "is_active": agent.is_active,
            "system_prompt": agent.system_prompt,
            "last_run": {
                "run_id": str(last_run.run_id) if last_run else None,
                "status": last_run.status if last_run else "IDLE",
                "started_at": last_run.started_at.isoformat() if last_run else None,
                "completed_at": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
                "summary": last_run.summary if last_run else None,
            } if last_run else None,
        })
    return result


@router.patch("/{agent_id}/config")
async def update_agent_config(
    agent_id: uuid.UUID,
    update: AgentConfigUpdate,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Updates configuration, autonomy level, or activation status of an agent."""
    res = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.agent_id == agent_id,
            AgentDefinition.tenant_id == tenant_id,
        )
    )
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent definition not found.")

    if update.autonomy_level is not None:
        agent.autonomy_level = update.autonomy_level
    if update.interval_seconds is not None:
        agent.interval_seconds = update.interval_seconds
    if update.is_active is not None:
        agent.is_active = update.is_active
    if update.system_prompt is not None:
        agent.system_prompt = update.system_prompt

    await session.commit()
    await session.refresh(agent)
    return {"status": "SUCCESS", "agent_id": str(agent.agent_id), "autonomy_level": agent.autonomy_level.value}


@router.post("/{slug}/run")
async def trigger_agent(
    slug: str,
    tenant_id: TenantIdDep,
):
    """Manually triggers an immediate execution cycle for a specific agent."""
    try:
        run = await orchestrator.run_agent(slug=slug, tenant_id=tenant_id, trigger_type="MANUAL")
        return {
            "status": "SUCCESS",
            "run_id": str(run.run_id),
            "agent_name": run.agent_name,
            "run_status": run.status,
            "summary": run.summary,
        }
    except Exception as e:
        logger.error(f"Agent trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-all")
async def trigger_all_agents(
    tenant_id: TenantIdDep,
):
    """Triggers an audit cycle across all 6 autonomous supervisors."""
    runs = await orchestrator.run_all_agents(tenant_id=tenant_id, trigger_type="MANUAL")
    return {
        "status": "SUCCESS",
        "total_triggered": len(runs),
        "results": [
            {"run_id": str(r.run_id), "agent": r.agent_name, "status": r.status, "summary": r.summary}
            for r in runs
        ],
    }


@router.get("/runs", response_model=List[Dict[str, Any]])
async def list_agent_runs(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    limit: int = Query(20, ge=1, le=100),
):
    """Lists historical agent execution runs."""
    res = await session.execute(
        select(AgentExecutionRun)
        .where(AgentExecutionRun.tenant_id == tenant_id)
        .order_by(desc(AgentExecutionRun.started_at))
        .limit(limit)
    )
    runs = res.scalars().all()
    return [
        {
            "run_id": str(r.run_id),
            "agent_name": r.agent_name,
            "trigger_type": r.trigger_type,
            "status": r.status,
            "summary": r.summary,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}/steps", response_model=List[Dict[str, Any]])
async def list_run_step_logs(
    run_id: uuid.UUID,
    session: DbSessionDep,
):
    """Returns the step-by-step reasoning trace and tool calls for a specific run."""
    res = await session.execute(
        select(AgentStepLog)
        .where(AgentStepLog.run_id == run_id)
        .order_by(AgentStepLog.step_number)
    )
    steps = res.scalars().all()
    return [
        {
            "step_id": str(s.step_id),
            "step_number": s.step_number,
            "node_name": s.node_name,
            "reasoning_thought": s.reasoning_thought,
            "tool_name": s.tool_name,
            "tool_arguments": s.tool_arguments,
            "tool_output": s.tool_output,
            "status": s.status,
            "duration_ms": s.duration_ms,
            "created_at": s.created_at.isoformat(),
        }
        for s in steps
    ]


@router.get("/communications", response_model=List[Dict[str, Any]])
async def list_communications(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    limit: int = Query(30, ge=1, le=100),
):
    """Lists outbound multi-channel communications (WhatsApp, Gmail, and Internal Ledger)."""
    res = await session.execute(
        select(AgentCommunication)
        .where(AgentCommunication.tenant_id == tenant_id)
        .order_by(desc(AgentCommunication.created_at))
        .limit(limit)
    )
    comms = res.scalars().all()
    return [
        {
            "comm_id": str(c.comm_id),
            "agent_name": c.agent_name,
            "channel": c.channel.value,
            "recipient": c.recipient,
            "subject": c.subject,
            "body": c.body,
            "status": c.status,
            "external_message_id": c.external_message_id,
            "created_at": c.created_at.isoformat(),
        }
        for c in comms
    ]
