"""Master Autonomous Agent Orchestrator."""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.supervisors.finance_compliance_agent import finance_compliance_agent
from erp.agents.supervisors.hr_workforce_agent import hr_workforce_agent
from erp.agents.supervisors.inventory_controller import inventory_controller
from erp.agents.supervisors.mes_quality_supervisor import mes_quality_supervisor
from erp.agents.supervisors.procurement_supervisor import procurement_supervisor
from erp.agents.supervisors.sales_sdr_agent import sales_sdr_agent
from erp.db.models.agents import AgentDefinition, AgentExecutionRun, AutonomyLevel
from erp.db.session import async_session_factory

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
            if agent_def and agent_def.autonomy_level == AutonomyLevel.DISABLED:
                raise ValueError(f"Agent '{agent_def.name}' is currently DISABLED.")

        logger.info(f"Triggering agent '{slug}' for tenant {tenant_id} (trigger: {trigger_type})")
        return await supervisor.execute_cycle(
            tenant_id=tenant_id,
            trigger_type=trigger_type,
            trigger_context=trigger_context,
        )

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
