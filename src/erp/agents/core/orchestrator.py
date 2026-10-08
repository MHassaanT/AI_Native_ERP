"""Master Autonomous Agent Orchestrator."""

import hashlib
import logging
import struct
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.supervisors.finance_compliance_agent import finance_compliance_agent
from erp.agents.supervisors.hr_workforce_agent import hr_workforce_agent
from erp.agents.supervisors.inventory_controller import inventory_controller
from erp.agents.supervisors.mes_quality_supervisor import mes_quality_supervisor
from erp.agents.supervisors.procurement_supervisor import procurement_supervisor
from erp.agents.supervisors.sales_sdr_agent import sales_sdr_agent
from erp.agents.core.llm_gateway import llm_gateway
from erp.db.models.agents import AgentDefinition, AgentExecutionRun, AutonomyLevel
from erp.db.session import async_session_factory
from erp.db.engine import async_engine

logger = logging.getLogger(__name__)

SUPERVISORS_MAP = {
    "procurement_supervisor": procurement_supervisor,
    "sales_sdr_agent": sales_sdr_agent,
    "inventory_controller": inventory_controller,
    "hr_workforce_agent": hr_workforce_agent,
    "mes_quality_supervisor": mes_quality_supervisor,
    "finance_compliance_agent": finance_compliance_agent,
}


class AgentOrchestrator:
    """Coordinates autonomous agent runs, schedules, and manual triggers."""

    async def run_agent(
        self,
        slug: str,
        tenant_id: uuid.UUID,
        trigger_type: str = "MANUAL",
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionRun:
        """Runs a specific agent by slug."""
        supervisor = SUPERVISORS_MAP.get(slug)
        if not supervisor:
            raise ValueError(f"Unknown agent supervisor slug: '{slug}'")

        # Verify agent is active and not disabled
        async with async_session_factory() as session:
            res = await session.execute(
                select(AgentDefinition).where(
                    AgentDefinition.tenant_id == tenant_id,
                    AgentDefinition.slug == slug,
                )
            )
            agent_def = res.scalar_one_or_none()
            if not agent_def:
                raise ValueError(f"Agent '{slug}' is not provisioned for this tenant.")
            if not agent_def.is_active or agent_def.autonomy_level == AutonomyLevel.DISABLED:
                raise ValueError(f"Agent '{agent_def.name}' is currently DISABLED.")
            agent_id = agent_def.agent_id
            agent_name = agent_def.name

        logger.info(f"Triggering agent '{slug}' for tenant {tenant_id} (trigger: {trigger_type})")
        digest = hashlib.sha256(f"{tenant_id}:{agent_id}".encode()).digest()[:8]
        lock_keys = struct.unpack(">ii", digest)
        async with async_engine.connect() as lock_connection:
            acquired = await lock_connection.scalar(
                select(func.pg_try_advisory_lock(*lock_keys))
            )
            await lock_connection.commit()
            if not acquired:
                raise RuntimeError(f"Agent '{slug}' already has a run in progress for this tenant.")

            started_monotonic = time.monotonic()
            dispatch_started_at = datetime.now(timezone.utc)
            llm_gateway.reset_usage()
            try:
                run = await supervisor.execute_cycle(
                    tenant_id=tenant_id,
                    trigger_type=trigger_type,
                    trigger_context=trigger_context,
                )
            except Exception as error:
                await self._record_failed_run(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    trigger_type=trigger_type,
                    trigger_context=trigger_context,
                    started_at=dispatch_started_at,
                    duration_ms=int((time.monotonic() - started_monotonic) * 1000),
                    error=error,
                    usage_metrics=llm_gateway.usage_snapshot(),
                )
                raise
            finally:
                await lock_connection.scalar(select(func.pg_advisory_unlock(*lock_keys)))
                await lock_connection.commit()

        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        usage_metrics = llm_gateway.usage_snapshot() or {}
        try:
            async with async_session_factory() as session:
                persisted = await session.get(AgentExecutionRun, run.run_id)
                if persisted:
                    metrics = dict(persisted.execution_metrics or {})
                    metrics.update(usage_metrics)
                    metrics["duration_ms"] = duration_ms
                    persisted.execution_metrics = metrics
                    await session.commit()
            run.execution_metrics = {
                **(run.execution_metrics or {}), **usage_metrics, "duration_ms": duration_ms
            }
        except Exception:
            logger.exception("Could not persist measured duration for run %s", run.run_id)
        return run

    async def _record_failed_run(
        self,
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        agent_name: str,
        trigger_type: str,
        trigger_context: Optional[Dict[str, Any]],
        started_at: datetime,
        duration_ms: int,
        error: Exception,
        usage_metrics: Optional[Dict[str, Any]],
    ) -> None:
        """Ensure a failed dispatch never leaves an execution row stuck RUNNING."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentExecutionRun)
                .where(
                    AgentExecutionRun.tenant_id == tenant_id,
                    AgentExecutionRun.agent_id == agent_id,
                    AgentExecutionRun.status == "RUNNING",
                    AgentExecutionRun.started_at >= started_at,
                )
                .order_by(AgentExecutionRun.started_at.desc())
                .limit(1)
                .with_for_update()
            )
            run = result.scalar_one_or_none()
            if run is None:
                run = AgentExecutionRun(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    trigger_type=trigger_type,
                    trigger_context=trigger_context or {},
                    started_at=started_at,
                )
                session.add(run)
            run.status = "FAILED"
            run.error_message = f"{type(error).__name__}: {error}"[:2000]
            run.completed_at = datetime.now(timezone.utc)
            run.execution_metrics = {**(usage_metrics or {}), "duration_ms": duration_ms}
            await session.commit()

    async def run_all_agents(
        self,
        tenant_id: uuid.UUID,
        trigger_type: str = "SCHEDULED",
    ) -> List[AgentExecutionRun]:
        """Runs all 6 autonomous supervisors sequentially."""
        runs = []
        for slug in SUPERVISORS_MAP.keys():
            try:
                run = await self.run_agent(slug=slug, tenant_id=tenant_id, trigger_type=trigger_type)
                runs.append(run)
            except Exception as e:
                logger.error(f"Error running agent '{slug}': {e}")
        return runs


orchestrator = AgentOrchestrator()
