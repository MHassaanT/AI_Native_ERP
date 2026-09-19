"""Dynamic Production Re-Routing Engine (PRD §Production Routing)."""

import logging
import time

from pydantic import BaseModel

from erp.production.cpsat_scheduler import (
    JobSpec,
    ScheduleResult,
    cpsat_scheduler,
)

logger = logging.getLogger(__name__)


class RerouteEventResult(BaseModel):
    faulted_workstation: str
    reallocated_operations_count: int
    new_makespan_minutes: int
    reroute_duration_seconds: float
    schedule: ScheduleResult


class DynamicProductionRouter:
    """Handles real-time machine failure triggers and dispatches instant CP-SAT rerouting."""

    @staticmethod
    def handle_workstation_failure(
        faulted_workstation_code: str,
        current_jobs: list[JobSpec],
        active_locked_machines: set[str] | None = None,
    ) -> RerouteEventResult:
        """Locks out faulted machine and re-runs CP-SAT solver across alternative qualified machinery."""
        start_t = time.perf_counter()

        locked = set(active_locked_machines or [])
        locked.add(faulted_workstation_code)

        # Count operations originally assigned to the faulted machine
        affected_ops_count = sum(
            1
            for job in current_jobs
            for op in job.operations
            if op.workstation_code == faulted_workstation_code
        )

        # Re-solve schedule with faulted machine locked out
        new_sched = cpsat_scheduler.solve_schedule(
            jobs=current_jobs,
            locked_workstations=locked,
            solver_timeout=10.0,
        )

        duration = round(time.perf_counter() - start_t, 3)
        logger.info(
            "Dynamic reroute completed in %.3fs for faulted %s (affected ops: %d, makespan: %dm)",
            duration,
            faulted_workstation_code,
            affected_ops_count,
            new_sched.makespan_minutes,
        )

        return RerouteEventResult(
            faulted_workstation=faulted_workstation_code,
            reallocated_operations_count=affected_ops_count,
            new_makespan_minutes=new_sched.makespan_minutes,
            reroute_duration_seconds=duration,
            schedule=new_sched,
        )


production_router = DynamicProductionRouter()
