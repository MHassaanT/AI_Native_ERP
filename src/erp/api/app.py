"""FastAPI Application Factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from erp.api.routes import (
    agents_router,
    ap_router,
    audit_soc2_router,
    auth_router,
    commercial_router,
    health_router,
    inventory_rop_router,
    iot_telemetry_router,
    ledger_router,
    mcp_router,
    production_schedule_router,
    quality_router,
    reconciliation_router,
    webhooks_router,
    workforce_router,
)
from erp.config import settings
from erp.events.email_gateway import email_gateway
from erp.events.producer import event_producer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and graceful shutdown."""
    logger.info("Initializing %s in %s mode...", settings.APP_NAME, settings.ENVIRONMENT)
    # Start Kafka/Redpanda Event Producer & Inbound Email Gateway
    await event_producer.start()
    email_gateway.start()
    yield
    # Graceful shutdown
    email_gateway.stop()
    await event_producer.stop()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Instantiates and configures the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Autonomous Multi-Agent Enterprise Resource Planning Core Engine",
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Route Handlers
    app.include_router(auth_router, prefix=settings.API_V1_STR)
    app.include_router(health_router, prefix=settings.API_V1_STR)
    app.include_router(ledger_router, prefix=settings.API_V1_STR)
    app.include_router(agents_router, prefix=settings.API_V1_STR)
    app.include_router(ap_router, prefix=settings.API_V1_STR)
    app.include_router(reconciliation_router, prefix=settings.API_V1_STR)
    app.include_router(mcp_router, prefix=settings.API_V1_STR)
    app.include_router(inventory_rop_router, prefix=settings.API_V1_STR)
    app.include_router(production_schedule_router, prefix=settings.API_V1_STR)
    app.include_router(iot_telemetry_router, prefix=settings.API_V1_STR)
    app.include_router(workforce_router, prefix=settings.API_V1_STR)
    app.include_router(commercial_router, prefix=settings.API_V1_STR)
    app.include_router(audit_soc2_router, prefix=settings.API_V1_STR)
    app.include_router(webhooks_router, prefix=settings.API_V1_STR)
    app.include_router(quality_router, prefix=settings.API_V1_STR)

    @app.get("/", include_in_schema=False)
    @app.get("/health", include_in_schema=False)
    async def root_ping():
        return {"status": "ok", "app": settings.APP_NAME, "docs": f"{settings.API_V1_STR}/docs"}

    return app


app = create_app()
