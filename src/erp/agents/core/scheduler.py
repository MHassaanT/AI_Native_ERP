"""Database-backed polling scheduler for tenant agent definitions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text

from erp.agents.core.orchestrator import orchestrator
from erp.auth.provisioning import ensure_agent_definitions
from erp.config import settings
from erp.db.models.agents import AgentDefinition, AgentExecutionRun, AutonomyLevel
from erp.db.models.tenant import Tenant
from erp.db.engine import async_engine
from erp.db.session import async_session_factory

logger = logging.getLogger(__name__)

# A session-level PostgreSQL advisory lock elects one scheduler across all API workers.
_SCHEDULER_LOCK_ID = 728194613


class AgentScheduler:
    """Polls active interval definitions and dispatches due tenant agent cycles."""

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                async with async_engine.connect() as lock_connection:
                    acquired = await lock_connection.scalar(
                        text("SELECT pg_try_advisory_lock(:lock_id)"),
                        {"lock_id": _SCHEDULER_LOCK_ID},
                    )
                    if acquired:
                        await lock_connection.commit()
                        logger.info("This process owns the agent scheduler lock.")
                        try:
                            await self._ensure_definitions()
                            await self._poll_until_stopped(stop_event)
                        finally:
                            await lock_connection.execute(
                                text("SELECT pg_advisory_unlock(:lock_id)"),
                                {"lock_id": _SCHEDULER_LOCK_ID},
                            )
                            await lock_connection.commit()
                        return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Agent scheduler iteration failed")

            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=settings.AGENT_SCHEDULER_POLL_SECONDS
                )
            except TimeoutError:
                pass

    async def _ensure_definitions(self) -> None:
        async with async_session_factory() as session:
            tenant_ids = (
                await session.execute(select(Tenant.tenant_id).where(Tenant.is_active.is_(True)))
            ).scalars().all()
            created = 0
            for tenant_id in tenant_ids:
                created += await ensure_agent_definitions(session, tenant_id)
            await session.commit()
            if created:
                logger.info("Provisioned %d missing agent definitions.", created)

    async def _poll_until_stopped(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self.run_due_agents_once()
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=settings.AGENT_SCHEDULER_POLL_SECONDS
                )
            except TimeoutError:
                pass

    async def run_due_agents_once(self) -> None:
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            definitions = (
                await session.execute(
                    select(AgentDefinition)
                    .join(Tenant, Tenant.tenant_id == AgentDefinition.tenant_id)
                    .where(
                        Tenant.is_active.is_(True),
                        AgentDefinition.is_active.is_(True),
                        AgentDefinition.autonomy_level != AutonomyLevel.DISABLED,
                        AgentDefinition.trigger_type.in_(("SCHEDULED", "INTERVAL")),
                        AgentDefinition.interval_seconds.is_not(None),
                        AgentDefinition.cron_expression.is_(None),
                    )
                )
            ).scalars().all()
            if not definitions:
                return

            agent_ids = [definition.agent_id for definition in definitions]
            last_runs = (
                await session.execute(
                    select(
                        AgentExecutionRun.agent_id,
                        func.max(AgentExecutionRun.started_at).label("last_started_at"),
                    )
                    .where(
                        AgentExecutionRun.agent_id.in_(agent_ids),
                        AgentExecutionRun.trigger_type.in_(("SCHEDULED", "INTERVAL")),
                    )
                    .group_by(AgentExecutionRun.agent_id)
                )
            ).all()
            last_by_agent = {row.agent_id: row.last_started_at for row in last_runs}

        for definition in definitions:
            interval = definition.interval_seconds or 300
            reference = last_by_agent.get(definition.agent_id) or definition.created_at
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            if now - reference < timedelta(seconds=interval):
                continue

            try:
                await orchestrator.run_agent(
                    slug=definition.slug,
                    tenant_id=definition.tenant_id,
                    trigger_type="SCHEDULED",
                    trigger_context={
                        "schedule_type": "INTERVAL",
                        "interval_seconds": interval,
                        "due_since": reference.isoformat(),
                    },
                )
            except Exception:
                logger.exception(
                    "Scheduled agent run failed for tenant=%s slug=%s",
                    definition.tenant_id,
                    definition.slug,
                )


agent_scheduler = AgentScheduler()
