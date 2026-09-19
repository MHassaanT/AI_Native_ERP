"""IoT Sensor Telemetry and Predictive Maintenance API Endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.manufacturing import MaintenanceTicket, Workstation
from erp.iot.predictive_maintenance import (
    MaintenanceActionPlan,
    maintenance_dispatcher,
)
from erp.iot.simulator import telemetry_simulator
from erp.iot.telemetry_stream import WorkstationTelemetryFrame

router = APIRouter(prefix="/iot", tags=["IoT Sensor Telemetry & Predictive Maintenance"])


class SimulateTelemetryRequest(BaseModel):
    workstation_code: str = "WS-INJECTION-01"
    inject_anomaly: bool = False
    inject_catastrophic: bool = False


class CreateTicketRequest(BaseModel):
    ticket_number: str = Field(..., min_length=2, max_length=64)
    workstation_code: str = Field(..., min_length=2, max_length=64)
    trigger_type: str = "MANUAL"
    fault_code: str | None = None
    description: str | None = None
    priority: str = "MEDIUM"


class UpdateTicketStatusRequest(BaseModel):
    status: str = "RESOLVED"


@router.get("/tickets", summary="List maintenance tickets")
async def list_maintenance_tickets(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns predictive and manual maintenance tickets from PostgreSQL."""
    stmt = (
        select(MaintenanceTicket, Workstation.workstation_code, Workstation.workstation_name)
        .join(Workstation, MaintenanceTicket.workstation_id == Workstation.workstation_id)
        .where(MaintenanceTicket.tenant_id == tenant_id)
        .order_by(MaintenanceTicket.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    tickets = []
    for t, ws_code, ws_name in rows:
        tickets.append(
            {
                "ticket_id": str(t.ticket_id),
                "ticket_number": t.ticket_number,
                "workstation_code": ws_code,
                "workstation_name": ws_name,
                "trigger_type": t.trigger_type,
                "fault_code": t.fault_code,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return tickets


@router.post("/tickets", status_code=status.HTTP_201_CREATED, summary="Create maintenance ticket")
async def create_maintenance_ticket(
    req: CreateTicketRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a manual or corrective maintenance ticket."""
    ws = (
        await db.execute(
            select(Workstation).where(
                Workstation.tenant_id == tenant_id,
                Workstation.workstation_code == req.workstation_code,
            )
        )
    ).scalar_one_or_none()

    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation '{req.workstation_code}' not found.",
        )

    ticket = MaintenanceTicket(
        tenant_id=tenant_id,
        ticket_number=req.ticket_number,
        workstation_id=ws.workstation_id,
        trigger_type=req.trigger_type,
        fault_code=req.fault_code,
        description=req.description,
        priority=req.priority,
        status="OPEN",
    )
    db.add(ticket)
    await db.flush()
    return ticket


@router.patch("/tickets/{ticket_id}", summary="Update maintenance ticket status")
async def update_ticket_status(
    ticket_id: uuid.UUID,
    req: UpdateTicketStatusRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Updates status of a maintenance ticket."""
    ticket = (
        await db.execute(
            select(MaintenanceTicket).where(
                MaintenanceTicket.tenant_id == tenant_id,
                MaintenanceTicket.ticket_id == ticket_id,
            )
        )
    ).scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    ticket.status = req.status.upper()
    await db.flush()
    return ticket


@router.post(
    "/telemetry",
    response_model=MaintenanceActionPlan,
    summary="Ingest high-frequency IoT sensor telemetry frame",
)
async def ingest_telemetry_frame(
    frame: WorkstationTelemetryFrame,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Evaluates telemetry frame; triggers predictive maintenance work order if failure probability >= 0.85."""
    return await maintenance_dispatcher.process_telemetry_frame(
        session=db,
        tenant_id=tenant_id,
        frame=frame,
    )


@router.post(
    "/simulate",
    response_model=WorkstationTelemetryFrame,
    summary="Simulate edge sensor telemetry reading",
)
async def simulate_sensor_reading(req: SimulateTelemetryRequest):
    """Generates synthetic vibration RMS, bearing temperature, and motor power readings."""
    return telemetry_simulator.generate_frame(
        workstation_code=req.workstation_code,
        inject_anomaly=req.inject_anomaly,
        inject_catastrophic=req.inject_catastrophic,
    )
