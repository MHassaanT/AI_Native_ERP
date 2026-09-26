"""API Routes Package."""

from erp.api.routes.agents import router as agents_router
from erp.api.routes.ap import router as ap_router
from erp.api.routes.audit_soc2 import router as audit_soc2_router
from erp.api.routes.auth import router as auth_router
from erp.api.routes.commercial import router as commercial_router
from erp.api.routes.health import router as health_router
from erp.api.routes.inventory_rop import router as inventory_rop_router
from erp.api.routes.iot_telemetry import router as iot_telemetry_router
from erp.api.routes.ledger import router as ledger_router
from erp.api.routes.mcp import router as mcp_router
from erp.api.routes.onboarding import router as onboarding_router
from erp.api.routes.production_schedule import router as production_schedule_router
from erp.api.routes.quality import router as quality_router
from erp.api.routes.reconciliation import router as reconciliation_router
from erp.api.routes.setup import router as setup_router
from erp.api.routes.webhooks import router as webhooks_router
from erp.api.routes.workforce import router as workforce_router

__all__ = [
    "auth_router",
    "setup_router",
    "onboarding_router",
    "health_router",
    "ledger_router",
    "agents_router",
    "ap_router",
    "reconciliation_router",
    "mcp_router",
    "inventory_rop_router",
    "production_schedule_router",
    "iot_telemetry_router",
    "workforce_router",
    "commercial_router",
    "audit_soc2_router",
    "webhooks_router",
    "quality_router",
]
