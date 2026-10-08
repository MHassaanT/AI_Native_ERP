"""Health and Readiness Probes."""

from fastapi import APIRouter, Request
from sqlalchemy import func, select, text

from erp.api.deps import DbSessionDep
from erp.db.models.outbox import TransactionalOutbox

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Basic service liveness check."""
    return {"status": "ok", "service": "ai-native-erp"}


@router.get("/ready")
async def readiness_check(db: DbSessionDep, request: Request):
    """Deep readiness probe checking database connectivity."""
    pending_outbox_events = None
    try:
        res = await db.execute(text("SELECT 1"))
        db_alive = res.scalar() == 1
        if db_alive:
            count_result = await db.execute(
                select(func.count()).select_from(TransactionalOutbox).where(
                    TransactionalOutbox.processed_at.is_(None)
                )
            )
            pending_outbox_events = count_result.scalar_one()
    except Exception:
        db_alive = False

    outbox_status = getattr(request.app.state, "outbox_dispatcher_status", "unknown")
    outbox_unavailable = outbox_status == "configured_but_kafka_unavailable"

    return {
        "status": "ready" if db_alive and not outbox_unavailable else "degraded",
        "database": "connected" if db_alive else "unreachable",
        "event_publishing_mode": getattr(request.app.state, "event_publishing_mode", "unknown"),
        "outbox_dispatcher_enabled": getattr(request.app.state, "outbox_dispatcher_enabled", False),
        "outbox_dispatcher_status": getattr(
            request.app.state, "outbox_dispatcher_status", "unknown"
        ),
        "pending_outbox_events": pending_outbox_events,
        "event_consumer_enabled": getattr(request.app.state, "event_consumer_enabled", False),
        "event_consumer_status": getattr(
            request.app.state, "event_consumer_status", "disabled_no_registered_domain_handlers"
        ),
    }
