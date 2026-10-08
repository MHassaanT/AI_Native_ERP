"""FastAPI Application Factory."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from erp.api.routes import (
    ap_router,
    assets_router,
    audit_soc2_router,
    auth_router,
    billing_router,
    commercial_router,
    crm_router,
    health_router,
    events_router,
    hr_router,
    inventory_rop_router,
    iot_telemetry_router,
    ledger_router,
    maintenance_router,
    mcp_router,
    onboarding_router,
    payroll_router,
    procurement_router,
    production_schedule_router,
    projects_router,
    quality_router,
    reconciliation_router,
    setup_router,
    stock_router,
    support_router,
    webhooks_router,
    workforce_router,
    reports_router,
    subcontracting_router,
    companies_router,
    currency_router,
    workflows_router,
)
from erp.config import settings
from erp.events.email_gateway import email_gateway
from erp.events.producer import event_producer
from erp.events.dispatcher import OutboxDispatcher
from erp.orchestration.persistence import mark_interrupted_dags_for_recovery

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and graceful shutdown."""
    logger.info("Initializing %s in %s mode...", settings.APP_NAME, settings.ENVIRONMENT)
    outbox_stop = asyncio.Event()
    outbox_task = None
    app.state.event_consumer_enabled = False
    app.state.event_consumer_status = "disabled_no_registered_domain_handlers"
    interrupted_dags = await mark_interrupted_dags_for_recovery()
    if interrupted_dags:
        logger.warning(
            "Marked %d interrupted DAG workflows for recovery review; no side effects were replayed.",
            interrupted_dags,
        )
    # Start Kafka/Redpanda Event Producer
    await event_producer.start()
    app.state.event_publishing_mode = "kafka" if event_producer.is_connected else "in_memory"
    if settings.ENABLE_OUTBOX_DISPATCHER and event_producer.is_connected:
        dispatcher = OutboxDispatcher(event_producer, settings.OUTBOX_DISPATCHER_POLL_SECONDS)
        outbox_task = asyncio.create_task(dispatcher.run(outbox_stop), name="transactional-outbox-dispatcher")
        app.state.outbox_dispatcher_enabled = True
        app.state.outbox_dispatcher_status = "running"
    elif settings.ENABLE_OUTBOX_DISPATCHER:
        app.state.outbox_dispatcher_enabled = False
        app.state.outbox_dispatcher_status = "configured_but_kafka_unavailable"
        logger.warning("Outbox dispatcher is enabled but Kafka is unavailable; outbox rows will remain pending.")
    else:
        app.state.outbox_dispatcher_enabled = False
        app.state.outbox_dispatcher_status = "disabled_by_configuration"
    if settings.ENABLE_SMTP_GATEWAY:
        email_gateway.start()
    yield
    # Graceful shutdown
    if settings.ENABLE_SMTP_GATEWAY:
        email_gateway.stop()
    if outbox_task:
        outbox_stop.set()
        await outbox_task
    await event_producer.stop()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Instantiates and configures the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Enterprise Resource Planning API",
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Route Handlers
    app.include_router(auth_router, prefix=settings.API_V1_STR)
    app.include_router(setup_router, prefix=settings.API_V1_STR)
    app.include_router(onboarding_router, prefix=settings.API_V1_STR)
    app.include_router(health_router, prefix=settings.API_V1_STR)
    app.include_router(events_router, prefix=settings.API_V1_STR)
    app.include_router(ledger_router, prefix=settings.API_V1_STR)
    app.include_router(billing_router, prefix=settings.API_V1_STR)
    app.include_router(workflows_router, prefix=settings.API_V1_STR)
    app.include_router(ap_router, prefix=settings.API_V1_STR)
    app.include_router(procurement_router, prefix=settings.API_V1_STR)
    app.include_router(reconciliation_router, prefix=settings.API_V1_STR)
    app.include_router(mcp_router, prefix=settings.API_V1_STR)
    app.include_router(inventory_rop_router, prefix=settings.API_V1_STR)
    app.include_router(production_schedule_router, prefix=settings.API_V1_STR)
    app.include_router(iot_telemetry_router, prefix=settings.API_V1_STR)
    app.include_router(workforce_router, prefix=settings.API_V1_STR)
    app.include_router(commercial_router, prefix=settings.API_V1_STR)
    app.include_router(stock_router, prefix=settings.API_V1_STR)
    app.include_router(hr_router, prefix=settings.API_V1_STR)
    app.include_router(payroll_router, prefix=settings.API_V1_STR)
    app.include_router(audit_soc2_router, prefix=settings.API_V1_STR)
    app.include_router(crm_router, prefix=settings.API_V1_STR)
    app.include_router(support_router, prefix=settings.API_V1_STR)
    app.include_router(webhooks_router, prefix=settings.API_V1_STR)
    app.include_router(quality_router, prefix=settings.API_V1_STR)
    app.include_router(assets_router, prefix=settings.API_V1_STR)
    app.include_router(projects_router, prefix=settings.API_V1_STR)
    app.include_router(maintenance_router, prefix=settings.API_V1_STR)
    app.include_router(reports_router, prefix=settings.API_V1_STR)
    app.include_router(subcontracting_router, prefix=settings.API_V1_STR)
    app.include_router(companies_router, prefix=settings.API_V1_STR)
    app.include_router(currency_router, prefix=settings.API_V1_STR)


    @app.get("/", include_in_schema=False)
    @app.get("/health", include_in_schema=False)
    async def root_ping():
        return {"status": "ok", "app": settings.APP_NAME, "docs": f"{settings.API_V1_STR}/docs"}

    return app


app = create_app()
