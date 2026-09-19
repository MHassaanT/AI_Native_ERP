"""Health and Readiness Probes."""

from fastapi import APIRouter
from sqlalchemy import text

from erp.api.deps import DbSessionDep

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Basic service liveness check."""
    return {"status": "ok", "service": "ai-native-erp"}


@router.get("/ready")
async def readiness_check(db: DbSessionDep):
    """Deep readiness probe checking database connectivity."""
    try:
        res = await db.execute(text("SELECT 1"))
        db_alive = res.scalar() == 1
    except Exception:
        db_alive = False

    return {
        "status": "ready" if db_alive else "degraded",
        "database": "connected" if db_alive else "unreachable",
    }
