"""Conflict arbitration is disabled until its inputs and side effects are record-backed.

The prior prototype accepted caller-supplied stock quantities and monetary values,
created synthetic stock rows, reserved stock without an idempotency record, and
reported customer notices without a delivery provider. Keep this module as an
explicit fail-closed boundary until a durable arbitration contract is implemented.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ArbitrationUnavailable(RuntimeError):
    """Raised when callers request the disabled prototype arbitration workflow."""


class MultiAgentArbitrationCoordinator:
    """Fail-closed placeholder for a future persisted-record arbitration workflow."""

    async def arbitrate_quality_vs_revenue(self, session: AsyncSession, tenant_id, req):
        raise ArbitrationUnavailable(
            "Conflict arbitration is unavailable until tenant-owned quality, stock, and order records are used."
        )


arbitration_coordinator = MultiAgentArbitrationCoordinator()
