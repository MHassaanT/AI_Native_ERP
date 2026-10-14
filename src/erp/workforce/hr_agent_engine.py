"""Autonomous HR Agent Engine.

Background task engine that periodically runs the HR recruitment
autonomous cycle, similar to the EAIWP workforce platform.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.session import async_session_factory
from erp.workflows.hr.recruitment_service import hr_recruitment_service

logger = logging.getLogger(__name__)


class HRAgentEngine:
    """Background engine for autonomous HR operations."""

    def __init__(self, cycle_interval_seconds: int = 300):
        self.cycle_interval = cycle_interval_seconds
        self._task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._tenant_ids: list[uuid.UUID] = []

    def register_tenant(self, tenant_id: uuid.UUID) -> None:
        """Register a tenant for autonomous processing."""
        if tenant_id not in self._tenant_ids:
            self._tenant_ids.append(tenant_id)
            logger.info(f"Registered tenant {tenant_id} for HR agent")

    def unregister_tenant(self, tenant_id: uuid.UUID) -> None:
        """Remove a tenant from autonomous processing."""
        if tenant_id in self._tenant_ids:
            self._tenant_ids.remove(tenant_id)

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the background engine."""
        if self.is_running:
            logger.warning("HR agent engine already running")
            return

        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"HR agent engine started (interval: {self.cycle_interval}s)")

    async def stop(self) -> None:
        """Stop the background engine."""
        if not self.is_running:
            return

        self._shutdown_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HR agent engine stopped")

    async def trigger_cycle(self, tenant_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Manually trigger an autonomous cycle."""
        tenants = [tenant_id] if tenant_id else self._tenant_ids

        if not tenants:
            # Default tenant for development
            tenants = [uuid.UUID("00000000-0000-0000-0000-000000000001")]

        all_results = {}
        for tid in tenants:
            result = await self._run_cycle_for_tenant(tid)
            all_results[str(tid)] = result

        return all_results

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        return {
            "running": self.is_running,
            "cycle_interval_seconds": self.cycle_interval,
            "registered_tenants": len(self._tenant_ids),
            "service_stats": hr_recruitment_service.stats,
        }

    async def _run_loop(self) -> None:
        """Main background loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.cycle_interval,
                )
            except asyncio.TimeoutError:
                # Time to run a cycle
                pass

            if self._shutdown_event.is_set():
                break

            for tenant_id in self._tenant_ids:
                try:
                    await self._run_cycle_for_tenant(tenant_id)
                except Exception as e:
                    logger.error(f"Cycle failed for tenant {tenant_id}: {e}")

    async def _run_cycle_for_tenant(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        """Run one autonomous cycle for a specific tenant."""
        logger.info(f"Running HR autonomous cycle for tenant {tenant_id}")

        async with async_session_factory() as db:
            try:
                result = await hr_recruitment_service.run_autonomous_cycle(
                    db=db,
                    tenant_id=tenant_id,
                )
                await db.commit()
                logger.info(f"Cycle complete for {tenant_id}: {result}")
                return result
            except Exception as e:
                await db.rollback()
                logger.error(f"Cycle failed for tenant {tenant_id}: {e}")
                raise


# Singleton instance
hr_agent_engine = HRAgentEngine(cycle_interval_seconds=300)
