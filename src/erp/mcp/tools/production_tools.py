"""Production Scheduling MCP Tool Bindings."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.production.cpsat_scheduler import JobOperationSpec, JobSpec, cpsat_scheduler
from erp.production.router import production_router


async def tool_solve_job_shop_schedule(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for solving job-shop schedule via Google OR-Tools CP-SAT solver."""
    jobs_data = arguments.get("jobs", [])
    jobs = [
        JobSpec(
            job_id=j["job_id"],
            job_name=j["job_name"],
            operations=[
                JobOperationSpec(
                    operation_id=op["operation_id"],
                    operation_name=op["operation_name"],
                    workstation_code=op["workstation_code"],
                    duration_minutes=op["duration_minutes"],
                    alternative_workstations=op.get("alternative_workstations", []),
                )
                for op in j["operations"]
            ],
        )
        for j in jobs_data
    ]

    locked = set(arguments.get("locked_workstations", []))
    res = cpsat_scheduler.solve_schedule(jobs=jobs, locked_workstations=locked)
    return res.model_dump(mode="json")


async def tool_isolate_workstation(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for locking out a machine and rerouting queued operations."""
    faulted_ws = arguments["workstation_code"]
    jobs_data = arguments.get("jobs", [])
    jobs = [
        JobSpec(
            job_id=j["job_id"],
            job_name=j["job_name"],
            operations=[
                JobOperationSpec(
                    operation_id=op["operation_id"],
                    operation_name=op["operation_name"],
                    workstation_code=op["workstation_code"],
                    duration_minutes=op["duration_minutes"],
                    alternative_workstations=op.get("alternative_workstations", []),
                )
                for op in j["operations"]
            ],
        )
        for j in jobs_data
    ]
    res = production_router.handle_workstation_failure(
        faulted_workstation_code=faulted_ws,
        current_jobs=jobs,
    )
    return res.model_dump(mode="json")
