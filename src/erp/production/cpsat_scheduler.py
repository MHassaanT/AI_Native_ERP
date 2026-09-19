"""Google OR-Tools CP-SAT Job-Shop Scheduler (PRD §Production Routing)."""

import logging
from typing import Any

from ortools.sat.python import cp_model
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScheduledOperation(BaseModel):
    job_id: str
    operation_id: str
    operation_name: str
    workstation_code: str
    duration_minutes: int
    start_minute: int
    end_minute: int


class ScheduleResult(BaseModel):
    solver_status: str  # OPTIMAL, FEASIBLE, INFEASIBLE
    makespan_minutes: int
    solve_time_seconds: float
    operations: list[ScheduledOperation]
    workstation_schedules: dict[str, list[ScheduledOperation]] = Field(default_factory=dict)


class JobOperationSpec(BaseModel):
    operation_id: str
    operation_name: str
    workstation_code: str
    duration_minutes: int
    alternative_workstations: list[str] = Field(default_factory=list)


class JobSpec(BaseModel):
    job_id: str
    job_name: str
    operations: list[JobOperationSpec]


class CPSATScheduler:
    """Solves multi-job multi-machine job-shop scheduling via Google OR-Tools CP-SAT."""

    SOLVER_TIMEOUT_SECONDS = 10.0

    def solve_schedule(
        self,
        jobs: list[JobSpec],
        locked_workstations: set[str] | None = None,
        solver_timeout: float | None = None,
    ) -> ScheduleResult:
        """Formulates and solves the job-shop constraint satisfaction problem."""
        locked = locked_workstations or set()
        timeout = solver_timeout or self.SOLVER_TIMEOUT_SECONDS

        model = cp_model.CpModel()

        # Upper bound on makespan (sum of all operation durations)
        horizon = sum(op.duration_minutes for job in jobs for op in job.operations) + 1440  # Buffer

        all_tasks: dict[tuple[str, str], dict[str, Any]] = {}
        machine_to_intervals: dict[str, list[cp_model.IntervalVar]] = {}

        # 1. Create Variables and Intervals
        for job in jobs:
            for op in job.operations:
                # Select available workstation (prefer default, or use alternative if locked)
                ws = op.workstation_code
                if ws in locked:
                    alternatives = [a for a in op.alternative_workstations if a not in locked]
                    if not alternatives:
                        logger.warning(
                            "No available machine for op %s (default %s locked)",
                            op.operation_id,
                            ws,
                        )
                        continue
                    ws = alternatives[0]

                suffix = f"_{job.job_id}_{op.operation_id}"
                start_var = model.NewIntVar(0, horizon, f"start{suffix}")
                end_var = model.NewIntVar(0, horizon, f"end{suffix}")
                interval_var = model.NewIntervalVar(
                    start_var, op.duration_minutes, end_var, f"interval{suffix}"
                )

                all_tasks[(job.job_id, op.operation_id)] = {
                    "start": start_var,
                    "end": end_var,
                    "interval": interval_var,
                    "workstation": ws,
                    "duration": op.duration_minutes,
                    "name": op.operation_name,
                }
                machine_to_intervals.setdefault(ws, []).append(interval_var)

        # 2. Add Disjunctive Non-Overlap Constraints per Machine
        for _ws, intervals in machine_to_intervals.items():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)

        # 3. Add Precedence Constraints within each Job
        for job in jobs:
            for i in range(len(job.operations) - 1):
                curr_key = (job.job_id, job.operations[i].operation_id)
                next_key = (job.job_id, job.operations[i + 1].operation_id)
                if curr_key in all_tasks and next_key in all_tasks:
                    model.Add(all_tasks[next_key]["start"] >= all_tasks[curr_key]["end"])

        # 4. Objective: Minimize Makespan
        makespan = model.NewIntVar(0, horizon, "makespan")
        if all_tasks:
            model.AddMaxEquality(makespan, [task["end"] for task in all_tasks.values()])
            model.Minimize(makespan)

        # 5. Solve with CP-SAT
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout
        status = solver.Solve(model)

        status_name = solver.StatusName(status)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            ops_result: list[ScheduledOperation] = []
            ws_map: dict[str, list[ScheduledOperation]] = {}

            for (job_id, op_id), task in all_tasks.items():
                s_min = int(solver.Value(task["start"]))
                e_min = int(solver.Value(task["end"]))
                ws = task["workstation"]

                scheduled = ScheduledOperation(
                    job_id=job_id,
                    operation_id=op_id,
                    operation_name=task["name"],
                    workstation_code=ws,
                    duration_minutes=task["duration"],
                    start_minute=s_min,
                    end_minute=e_min,
                )
                ops_result.append(scheduled)
                ws_map.setdefault(ws, []).append(scheduled)

            # Sort by start time
            ops_result.sort(key=lambda o: (o.start_minute, o.workstation_code))
            for op_list in ws_map.values():
                op_list.sort(key=lambda o: o.start_minute)

            return ScheduleResult(
                solver_status=status_name,
                makespan_minutes=int(solver.Value(makespan)),
                solve_time_seconds=round(solver.WallTime(), 3),
                operations=ops_result,
                workstation_schedules=ws_map,
            )

        return ScheduleResult(
            solver_status=status_name,
            makespan_minutes=0,
            solve_time_seconds=round(solver.WallTime(), 3),
            operations=[],
            workstation_schedules={},
        )


cpsat_scheduler = CPSATScheduler()
