"""API Routes Package."""

from erp.api.routes.ap import router as ap_router
from erp.api.routes.assets import router as assets_router
from erp.api.routes.audit_soc2 import router as audit_soc2_router
from erp.api.routes.auth import router as auth_router
from erp.api.routes.billing import router as billing_router
from erp.api.routes.commercial import router as commercial_router
from erp.api.routes.crm import router as crm_router
from erp.api.routes.health import router as health_router
from erp.api.routes.events import router as events_router
from erp.api.routes.hr import router as hr_router
from erp.api.routes.inventory_rop import router as inventory_rop_router
from erp.api.routes.iot_telemetry import router as iot_telemetry_router
from erp.api.routes.ledger import router as ledger_router
from erp.api.routes.maintenance import router as maintenance_router
from erp.api.routes.mcp import router as mcp_router
from erp.api.routes.onboarding import router as onboarding_router
from erp.api.routes.payroll import router as payroll_router
from erp.api.routes.procurement import router as procurement_router
from erp.api.routes.production_schedule import router as production_schedule_router
from erp.api.routes.projects import router as projects_router
from erp.api.routes.quality import router as quality_router
from erp.api.routes.reconciliation import router as reconciliation_router
from erp.api.routes.setup import router as setup_router
from erp.api.routes.stock import router as stock_router
from erp.api.routes.support import router as support_router
from erp.api.routes.webhooks import router as webhooks_router
from erp.api.routes.workforce import router as workforce_router
from erp.api.routes.reports import router as reports_router
from erp.api.routes.subcontracting import router as subcontracting_router
from erp.api.routes.companies import router as companies_router
from erp.api.routes.currency import router as currency_router
from erp.api.routes.workflows import router as workflows_router

__all__ = [
    "ap_router",
    "assets_router",
    "audit_soc2_router",
    "auth_router",
    "billing_router",
    "commercial_router",
    "crm_router",
    "health_router",
    "events_router",
    "hr_router",
    "inventory_rop_router",
    "iot_telemetry_router",
    "ledger_router",
    "maintenance_router",
    "mcp_router",
    "onboarding_router",
    "payroll_router",
    "procurement_router",
    "production_schedule_router",
    "projects_router",
    "quality_router",
    "reconciliation_router",
    "setup_router",
    "stock_router",
    "support_router",
    "webhooks_router",
    "workforce_router",
    "workflows_router",
    "reports_router",
    "subcontracting_router",
    "companies_router",
    "currency_router",
]
