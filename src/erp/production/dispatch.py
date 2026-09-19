"""Shop-Floor Workstation Queue and Dispatch Manager."""

from pydantic import BaseModel, Field

from erp.production.cpsat_scheduler import ScheduledOperation


class WorkstationQueue(BaseModel):
    workstation_code: str
    is_active: bool = True
    active_operation: ScheduledOperation | None = None
    queued_operations: list[ScheduledOperation] = Field(default_factory=list)


class DispatchManager:
    """Maintains real-time state of shop-floor machines and queued operations."""

    def __init__(self):
        self.queues: dict[str, WorkstationQueue] = {}

    def update_from_schedule(
        self, workstation_schedules: dict[str, list[ScheduledOperation]]
    ) -> None:
        """Updates workstation dispatch queues from an optimized CP-SAT schedule."""
        for ws_code, ops in workstation_schedules.items():
            if not ops:
                continue
            active = ops[0] if ops else None
            queued = ops[1:] if len(ops) > 1 else []
            self.queues[ws_code] = WorkstationQueue(
                workstation_code=ws_code,
                is_active=True,
                active_operation=active,
                queued_operations=queued,
            )

    def lock_workstation(self, workstation_code: str) -> list[ScheduledOperation]:
        """Locks a machine due to fault and returns evacuated operations for rerouting."""
        queue = self.queues.get(workstation_code)
        if not queue:
            return []
        queue.is_active = False
        evacuated = []
        if queue.active_operation:
            evacuated.append(queue.active_operation)
            queue.active_operation = None
        evacuated.extend(queue.queued_operations)
        queue.queued_operations = []
        return evacuated


dispatch_manager = DispatchManager()
