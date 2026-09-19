"""Predictive Maintenance Dispatcher and Spare Parts Coordinator (PRD §Equipment Maintenance)."""

import logging
import uuid
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import Item, StockLevel
from erp.db.models.manufacturing import MaintenanceTicket, Workstation
from erp.events.outbox import OutboxManager
from erp.iot.anomaly_detector import anomaly_detector
from erp.iot.telemetry_stream import WorkstationTelemetryFrame

logger = logging.getLogger(__name__)


class MaintenanceActionPlan(BaseModel):
    workstation_code: str
    failure_probability: float
    work_order_created: bool
    ticket_number: str | None = None
    spare_parts_available: bool = True
    expedited_po_required: bool = False
    emergency_lockout: bool = False
    alarm_summary: str
    rerouted: bool = False



class PredictiveMaintenanceDispatcher:
    """Automates maintenance ticket dispatching and spare parts replenishment before equipment failure."""

    FAILURE_THRESHOLD_48H = 0.85

    async def process_telemetry_frame(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        frame: WorkstationTelemetryFrame,
    ) -> MaintenanceActionPlan:
        """Evaluates telemetry frame; creates maintenance ticket and reserves spare parts if degraded."""
        eval_result = anomaly_detector.evaluate_telemetry(frame)

        if eval_result.failure_probability < self.FAILURE_THRESHOLD_48H:
            return MaintenanceActionPlan(
                workstation_code=frame.workstation_code,
                failure_probability=eval_result.failure_probability,
                work_order_created=False,
                alarm_summary="Nominal conditions",
            )

        # 1. Fetch Workstation
        ws_stmt = select(Workstation).where(
            Workstation.tenant_id == tenant_id,
            Workstation.workstation_code == frame.workstation_code,
        )
        ws = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not ws:
            raise ValueError(f"Workstation '{frame.workstation_code}' not found.")

        # 2. Check Spare Parts (e.g. BEARING-SPINDLE-6004)
        part_stmt = select(Item).where(
            Item.tenant_id == tenant_id,
            Item.item_code.like("%BEARING%"),
        )
        spare_item = (await session.execute(part_stmt)).scalar_one_or_none()

        spare_available = True
        expedited_po = False

        if spare_item:
            stock_stmt = select(func.sum(StockLevel.current_qty)).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == spare_item.item_id,
            )
            spare_qty = (await session.execute(stock_stmt)).scalar() or Decimal("0.0000")
            if spare_qty < Decimal("1.0000"):
                spare_available = False
                expedited_po = True
                logger.warning(
                    "Spare parts out of stock for %s. Triggering expedited PO.",
                    frame.workstation_code,
                )

        # 3. Create Maintenance Work Order
        ticket_no = f"MNT-{uuid.uuid4().hex[:6].upper()}"
        ticket = MaintenanceTicket(
            tenant_id=tenant_id,
            ticket_number=ticket_no,
            workstation_id=ws.workstation_id,
            priority="CRITICAL" if eval_result.is_catastrophic else "HIGH",
            description="; ".join(eval_result.alarm_reasons),
            status="SCHEDULED",

        )
        session.add(ticket)

        # 4. If catastrophic, lock machine
        if eval_result.is_catastrophic:
            ws.status = "CRITICAL_FAULT"
            logger.error(
                "Catastrophic machine fault on %s. Status set to CRITICAL_FAULT.",
                ws.workstation_code,
            )

        # 5. Outbox event
        await OutboxManager.enqueue_event(
            session=session,
            tenant_id=tenant_id,
            aggregate_type="MAINTENANCE_TICKET",
            aggregate_id=str(ticket.ticket_id),
            event_type="erp.production.machine_fault",
            payload={
                "ticket_number": ticket_no,
                "workstation_code": ws.workstation_code,
                "priority": ticket.priority,
                "vibration_rms": frame.vibration_rms_mm_s,
                "bearing_temp_c": frame.bearing_temp_c,
                "failure_probability": eval_result.failure_probability,
                "expedited_po_required": expedited_po,
            },
        )

        await session.flush()

        return MaintenanceActionPlan(
            workstation_code=frame.workstation_code,
            failure_probability=eval_result.failure_probability,
            work_order_created=True,
            ticket_number=ticket_no,
            spare_parts_available=spare_available,
            expedited_po_required=expedited_po,
            emergency_lockout=eval_result.is_catastrophic,
            alarm_summary="; ".join(eval_result.alarm_reasons),
        )


maintenance_dispatcher = PredictiveMaintenanceDispatcher()
