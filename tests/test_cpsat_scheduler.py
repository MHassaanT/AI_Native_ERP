"""Unit and Benchmark Tests for Google OR-Tools CP-SAT Job-Shop Scheduler."""

from erp.production.cpsat_scheduler import (
    JobOperationSpec,
    JobSpec,
    cpsat_scheduler,
)
from erp.production.router import production_router


class TestCPSATScheduler:
    """Tests constraint programming makespan optimization and dynamic machine rerouting."""

    def test_cpsat_job_shop_makespan_optimization(self):
        jobs = [
            JobSpec(
                job_id="JOB-1",
                job_name="Hydraulic Valve Body",
                operations=[
                    JobOperationSpec(
                        operation_id="OP-10",
                        operation_name="Turning",
                        workstation_code="WS-CNC-01",
                        duration_minutes=30,
                    ),
                    JobOperationSpec(
                        operation_id="OP-20",
                        operation_name="Milling",
                        workstation_code="WS-MILL-01",
                        duration_minutes=40,
                    ),
                ],
            ),
            JobSpec(
                job_id="JOB-2",
                job_name="Actuator Piston",
                operations=[
                    JobOperationSpec(
                        operation_id="OP-10",
                        operation_name="Turning",
                        workstation_code="WS-CNC-01",
                        duration_minutes=25,
                    ),
                    JobOperationSpec(
                        operation_id="OP-20",
                        operation_name="Grinding",
                        workstation_code="WS-GRIND-01",
                        duration_minutes=35,
                    ),
                ],
            ),
        ]

        result = cpsat_scheduler.solve_schedule(jobs=jobs)

        assert result.solver_status in ("OPTIMAL", "FEASIBLE")
        assert result.makespan_minutes > 0
        assert result.solve_time_seconds <= 10.0  # Under 10s PRD limit

        # Verify Disjunctive NoOverlap on WS-CNC-01
        cnc_ops = [op for op in result.operations if op.workstation_code == "WS-CNC-01"]
        assert len(cnc_ops) == 2
        cnc_ops.sort(key=lambda o: o.start_minute)
        # End of first operation must be <= Start of second operation
        assert cnc_ops[0].end_minute <= cnc_ops[1].start_minute

        # Verify Precedence within JOB-1
        job1_ops = {op.operation_id: op for op in result.operations if op.job_id == "JOB-1"}
        assert job1_ops["OP-20"].start_minute >= job1_ops["OP-10"].end_minute

    def test_dynamic_workstation_failure_rerouting(self):
        """PRD Acceptance Criteria: Machine fault triggers rescheduling within <= 15 seconds."""
        jobs = [
            JobSpec(
                job_id="JOB-A",
                job_name="Enclosure Plate",
                operations=[
                    JobOperationSpec(
                        operation_id="OP-1",
                        operation_name="High Speed Profiling",
                        workstation_code="WS-CNC-01",
                        duration_minutes=45,
                        alternative_workstations=["WS-CNC-02"],
                    ),
                ],
            ),
            JobSpec(
                job_id="JOB-B",
                job_name="Mounting Bracket",
                operations=[
                    JobOperationSpec(
                        operation_id="OP-1",
                        operation_name="Drill & Tap",
                        workstation_code="WS-CNC-01",
                        duration_minutes=30,
                        alternative_workstations=["WS-CNC-02"],
                    ),
                ],
            ),
        ]

        # Simulate WS-CNC-01 catastrophic failure
        reroute_result = production_router.handle_workstation_failure(
            faulted_workstation_code="WS-CNC-01",
            current_jobs=jobs,
        )

        assert reroute_result.faulted_workstation == "WS-CNC-01"
        assert reroute_result.reallocated_operations_count == 2
        assert reroute_result.reroute_duration_seconds <= 15.0  # PRD requirement: <= 15s

        # All operations should now be scheduled on alternative WS-CNC-02
        for op in reroute_result.schedule.operations:
            assert op.workstation_code == "WS-CNC-02"
            assert op.workstation_code != "WS-CNC-01"
