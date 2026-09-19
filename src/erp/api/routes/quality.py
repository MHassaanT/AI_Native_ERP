"""Edge Vision Quality Control & PLC Scrap Diversion API (PRD §Quality Control).

Enforces real-time optical inspection classification, sub-200ms pneumatic diverter
actuation, rolling defect rate calculation, and multi-tenant lot quarantining.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.iot.mqtt_bridge import iot_bridge
from erp.quality.defect_evaluator import EdgeQualityEvaluator
from erp.quality.lot_quarantine import lot_quarantine_manager
from erp.quality.plc_diverter import plc_diverter

router = APIRouter(prefix="/quality", tags=["Edge Quality & PLC Scrap Diversion"])


class InspectionRequest(BaseModel):
    item_code: str = "FG-ENCLOSURE-IP67"
    lot_number: str = Field(..., min_length=2, max_length=64)
    workstation_code: str = "WS-LINE-01"
    defect_type: str = "SURFACE_CRACK"  # NONE, SURFACE_CRACK, DIMENSIONAL_VARIANCE, VOID, COLOR_DRIFT
    confidence_score: float = Field(0.99, ge=0.0, le=1.0)


class ReleaseLotRequest(BaseModel):
    lot_number: str = Field(..., min_length=2, max_length=64)
    release_notes: str = "Re-inspected by QA Lead; cleared for production"


@router.get("/telemetry", summary="Get edge machine & quality telemetry")
async def get_quality_telemetry():
    """Returns real-time edge telemetry, rolling defect rate, and pneumatic diverter status."""
    summary = iot_bridge.get_summary()
    buffer = iot_bridge.get_latest_telemetry()
    diverter = plc_diverter.get_diverter_status()

    return {
        "summary": summary,
        "history": buffer,
        "diverter": diverter,
    }


@router.post("/inspect", summary="Submit optical defect inspection & trigger PLC diverter")
async def submit_optical_inspection(
    req: InspectionRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Evaluates optical defect frame, trips hardware diverter (<200ms) if confidence > 0.98, and quarantines lot."""
    insp_id = f"insp_{uuid.uuid4().hex[:10]}"

    classification = EdgeQualityEvaluator.evaluate_inspection(
        inspection_id=insp_id,
        item_code=req.item_code,
        lot_number=req.lot_number,
        workstation_code=req.workstation_code,
        defect_type=req.defect_type,
        confidence_score=req.confidence_score,
    )

    diverter_record = None
    if classification.trigger_plc_scrap_trip:
        diverter_record = await plc_diverter.execute_scrap_trip(
            inspection_id=insp_id,
            workstation_code=req.workstation_code,
        )

    quarantine_res = await lot_quarantine_manager.record_inspection_and_evaluate_quarantine(
        session=db,
        tenant_id=tenant_id,
        classification=classification,
    )

    # Ingest into IoT bridge
    vibration = 3.8 if classification.is_defective else 1.45
    temp_c = 72.0 if classification.is_defective else 64.5
    iot_bridge.record_reading(
        workstation_code=req.workstation_code,
        speed_rpm=1450.0,
        temp_c=temp_c,
        vibration=vibration,
        is_scrap=classification.trigger_plc_scrap_trip,
    )

    return {
        "classification": classification.model_dump(),
        "quarantine": quarantine_res.model_dump(),
        "diverter_trip": diverter_record.model_dump() if diverter_record else None,
    }


@router.get("/lots", summary="List quarantined inventory lots")
async def list_quarantined_lots():
    """Returns all currently quarantined lots held from dispatch."""
    lots = []
    for lot in lot_quarantine_manager.quarantined_lots:
        lots.append({
            "lot_number": lot,
            "status": "QUARANTINED",
            "reason": "Edge optical inspection defect exceeded 0.98 confidence threshold",
            "item_code": "FG-ENCLOSURE-IP67",
            "quarantined_workstation": "WS-LINE-01",
        })
    return lots


@router.post("/release-lot", summary="Release quarantined lot back into production")
async def release_quarantined_lot(
    req: ReleaseLotRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Releases quarantined lot back into available stock and updates database flags."""
    from sqlalchemy import select
    from erp.db.models.inventory import StockLevel

    stk_stmt = select(StockLevel).where(
        StockLevel.tenant_id == tenant_id,
        StockLevel.lot_number == req.lot_number,
    )
    matching_stks = (await db.execute(stk_stmt)).scalars().all()
    for s in matching_stks:
        s.is_quarantined = False

    if req.lot_number in lot_quarantine_manager.quarantined_lots:
        lot_quarantine_manager.quarantined_lots.remove(req.lot_number)

    await db.flush()
    return {
        "lot_number": req.lot_number,
        "status": "RELEASED",
        "message": f"Lot {req.lot_number} successfully released from quarantine hold.",
    }


@router.post(
    "/arbitrate-conflict",
    summary="Arbitrate Quality statutory quarantine vs Revenue VIP shipment conflict",
)
async def arbitrate_quarantine_conflict(
    req: dict[str, Any],
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Arbitrates conflicting agent claims and triggers revenue fallback re-route or customer notice."""
    from decimal import Decimal
    import uuid
    from erp.orchestration.arbitration_coordinator import (
        ConflictArbitrationRequest,
        arbitration_coordinator,
    )

    arb_req = ConflictArbitrationRequest(
        lot_number=req["lot_number"],
        item_id=uuid.UUID(str(req["item_id"])),
        warehouse_id=uuid.UUID(str(req["warehouse_id"])),
        order_id=uuid.UUID(str(req["order_id"])),
        customer_id=uuid.UUID(str(req["customer_id"])),
        order_quantity=Decimal(str(req.get("order_quantity", "100.0000"))),
        order_monetary_value=Decimal(str(req.get("order_monetary_value", "50000.00"))),
        defect_type=req.get("defect_type", "SURFACE_CRACK"),
        defect_confidence=float(req.get("defect_confidence", 0.99)),
    )

    report = await arbitration_coordinator.arbitrate_quality_vs_revenue(
        session=db,
        tenant_id=tenant_id,
        req=arb_req,
    )
    return report.model_dump()

