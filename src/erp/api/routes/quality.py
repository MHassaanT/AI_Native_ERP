"""Edge Vision Quality Control & ERPNext Quality Management Suite.

Enforces real-time optical inspection classification, pneumatic diverter actuation,
plus standard inspection templates, reading tolerance verification, Non-Conformance
Reports (NCR), and Corrective & Preventive Action (CAPA) with 5-Whys root cause analysis.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.iot.mqtt_bridge import iot_bridge
from erp.quality.defect_evaluator import EdgeQualityEvaluator
from erp.quality.lot_quarantine import lot_quarantine_manager
from erp.quality.plc_diverter import plc_diverter
from erp.workflows.quality import quality_service

router = APIRouter(prefix="/quality", tags=["Quality Management & Edge Control"])


# -----------------------------------------------------------------------------
# IoT & Optical Inspection Endpoints (Preserved)
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# ERPNext Quality Management Suite (Templates, Inspections, NCR & CAPA)
# -----------------------------------------------------------------------------

class CreateTemplateSchema(BaseModel):
    template_name: str
    description: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None


class CreateInspectionSchema(BaseModel):
    inspection_number: str
    inspection_type: str = "INCOMING"
    reference_doc_type: str = "PurchaseReceipt"
    reference_doc_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    item_code: str
    sample_size: Decimal = Decimal("1.0000")
    inspected_by_id: Optional[uuid.UUID] = None
    inspection_date: Optional[date] = None
    readings: Optional[List[Dict[str, Any]]] = None
    remarks: Optional[str] = None
    auto_create_nc_on_failure: bool = True


class CreateNonConformanceSchema(BaseModel):
    nc_number: str
    title: str
    source_type: str = "INSPECTION"
    inspection_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    item_code: Optional[str] = None
    severity: str = "MAJOR"
    description: str = ""
    immediate_disposition: str = "REWORK"
    status: str = "OPEN"


class CreateQualityActionSchema(BaseModel):
    capa_number: str
    nc_id: uuid.UUID
    action_type: str = "CORRECTIVE"
    root_cause_analysis: str
    action_plan: str
    target_completion_date: date
    assigned_to_id: Optional[uuid.UUID] = None


class ResolveQualityActionSchema(BaseModel):
    resolution_notes: str
    new_status: str = "VERIFIED_CLOSED"


# Template Endpoints
@router.post("/templates", status_code=status.HTTP_201_CREATED, summary="Create Quality Inspection Template")
async def create_template(req: CreateTemplateSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    tmpl = await quality_service.create_template(
        session=db,
        tenant_id=tenant_id,
        template_name=req.template_name,
        description=req.description,
        parameters=req.parameters,
    )
    return {"template_id": tmpl.template_id, "template_name": tmpl.template_name}


@router.get("/templates", summary="List Quality Inspection Templates")
async def list_templates(tenant_id: TenantIdDep, db: DbSessionDep):
    tmpls = await quality_service.list_templates(db, tenant_id)
    return [
        {
            "template_id": t.template_id,
            "template_name": t.template_name,
            "description": t.description,
            "parameters": [
                {
                    "parameter_name": p.parameter_name,
                    "specification": p.specification,
                    "min_value": float(p.min_value) if p.min_value is not None else None,
                    "max_value": float(p.max_value) if p.max_value is not None else None,
                }
                for p in t.parameters
            ],
        }
        for t in tmpls
    ]


@router.get("/templates/{template_id}", summary="Get Quality Inspection Template")
async def get_template(template_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    t = await quality_service.get_template(db, tenant_id, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": t.template_id,
        "template_name": t.template_name,
        "description": t.description,
        "parameters": [
            {
                "parameter_id": p.parameter_id,
                "parameter_name": p.parameter_name,
                "specification": p.specification,
                "min_value": float(p.min_value) if p.min_value is not None else None,
                "max_value": float(p.max_value) if p.max_value is not None else None,
            }
            for p in t.parameters
        ],
    }


# Inspection Endpoints
@router.post("/inspections", status_code=status.HTTP_201_CREATED, summary="Create Quality Inspection")
async def create_inspection(req: CreateInspectionSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    insp = await quality_service.create_inspection(
        session=db,
        tenant_id=tenant_id,
        inspection_number=req.inspection_number,
        inspection_type=req.inspection_type,
        reference_doc_type=req.reference_doc_type,
        item_code=req.item_code,
        sample_size=req.sample_size,
        reference_doc_id=req.reference_doc_id,
        item_id=req.item_id,
        inspected_by_id=req.inspected_by_id,
        inspection_date=req.inspection_date,
        readings=req.readings,
        remarks=req.remarks,
        auto_create_nc_on_failure=req.auto_create_nc_on_failure,
    )
    return {
        "inspection_id": insp.inspection_id,
        "inspection_number": insp.inspection_number,
        "status": insp.status,
        "readings": insp.readings,
    }


@router.get("/inspections", summary="List Quality Inspections")
async def list_inspections(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    inspection_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    insps = await quality_service.list_inspections(db, tenant_id, inspection_type=inspection_type, status=status)
    return [
        {
            "inspection_id": i.inspection_id,
            "inspection_number": i.inspection_number,
            "inspection_type": i.inspection_type,
            "reference_doc_type": i.reference_doc_type,
            "item_code": i.item_code,
            "sample_size": float(i.sample_size),
            "inspection_date": str(i.inspection_date),
            "status": i.status,
            "remarks": i.remarks,
        }
        for i in insps
    ]


@router.get("/inspections/{inspection_id}", summary="Get Quality Inspection")
async def get_inspection(inspection_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    i = await quality_service.get_inspection(db, tenant_id, inspection_id)
    if not i:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {
        "inspection_id": i.inspection_id,
        "inspection_number": i.inspection_number,
        "inspection_type": i.inspection_type,
        "reference_doc_type": i.reference_doc_type,
        "item_code": i.item_code,
        "sample_size": float(i.sample_size),
        "inspection_date": str(i.inspection_date),
        "status": i.status,
        "readings": i.readings,
        "remarks": i.remarks,
        "non_conformances": [
            {
                "nc_id": nc.nc_id,
                "nc_number": nc.nc_number,
                "severity": nc.severity,
                "status": nc.status,
            }
            for nc in i.non_conformances
        ],
    }


# Non-Conformance Endpoints
@router.post("/non-conformances", status_code=status.HTTP_201_CREATED, summary="Create Non-Conformance Report (NCR)")
async def create_non_conformance(req: CreateNonConformanceSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    nc = await quality_service.create_non_conformance(
        session=db,
        tenant_id=tenant_id,
        nc_number=req.nc_number,
        title=req.title,
        source_type=req.source_type,
        inspection_id=req.inspection_id,
        item_id=req.item_id,
        item_code=req.item_code,
        severity=req.severity,
        description=req.description,
        immediate_disposition=req.immediate_disposition,
        status=req.status,
    )
    return {"nc_id": nc.nc_id, "nc_number": nc.nc_number, "severity": nc.severity, "status": nc.status}


@router.get("/non-conformances", summary="List Non-Conformance Reports")
async def list_non_conformances(tenant_id: TenantIdDep, db: DbSessionDep, status: Optional[str] = Query(None)):
    ncs = await quality_service.list_non_conformances(db, tenant_id, status=status)
    return [
        {
            "nc_id": n.nc_id,
            "nc_number": n.nc_number,
            "title": n.title,
            "source_type": n.source_type,
            "item_code": n.item_code,
            "severity": n.severity,
            "immediate_disposition": n.immediate_disposition,
            "status": n.status,
            "action_count": len(n.actions),
        }
        for n in ncs
    ]


@router.get("/non-conformances/{nc_id}", summary="Get Non-Conformance Report")
async def get_non_conformance(nc_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    nc = await quality_service.get_non_conformance(db, tenant_id, nc_id)
    if not nc:
        raise HTTPException(status_code=404, detail="Non-conformance report not found")
    return {
        "nc_id": nc.nc_id,
        "nc_number": nc.nc_number,
        "title": nc.title,
        "source_type": nc.source_type,
        "item_code": nc.item_code,
        "severity": nc.severity,
        "description": nc.description,
        "immediate_disposition": nc.immediate_disposition,
        "status": nc.status,
        "actions": [
            {
                "action_id": a.action_id,
                "capa_number": a.capa_number,
                "action_type": a.action_type,
                "root_cause_analysis": a.root_cause_analysis,
                "action_plan": a.action_plan,
                "target_completion_date": str(a.target_completion_date),
                "status": a.status,
            }
            for a in nc.actions
        ],
    }


# CAPA Endpoints
@router.post("/actions", status_code=status.HTTP_201_CREATED, summary="Create CAPA (5-Whys Analysis)")
async def create_action(req: CreateQualityActionSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        action = await quality_service.create_action(
            session=db,
            tenant_id=tenant_id,
            capa_number=req.capa_number,
            nc_id=req.nc_id,
            action_type=req.action_type,
            root_cause_analysis=req.root_cause_analysis,
            action_plan=req.action_plan,
            target_completion_date=req.target_completion_date,
            assigned_to_id=req.assigned_to_id,
        )
        return {
            "action_id": action.action_id,
            "capa_number": action.capa_number,
            "action_type": action.action_type,
            "status": action.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/actions/{action_id}/resolve", summary="Resolve & Close CAPA Action")
async def resolve_action(action_id: uuid.UUID, req: ResolveQualityActionSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        a = await quality_service.resolve_action(
            session=db,
            tenant_id=tenant_id,
            action_id=action_id,
            resolution_notes=req.resolution_notes,
            new_status=req.new_status,
        )
        return {
            "action_id": a.action_id,
            "capa_number": a.capa_number,
            "status": a.status,
            "resolution_notes": a.resolution_notes,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/actions", summary="List Quality CAPA Actions")
async def list_actions(tenant_id: TenantIdDep, db: DbSessionDep, status: Optional[str] = Query(None)):
    actions = await quality_service.list_actions(db, tenant_id, status=status)
    return [
        {
            "action_id": a.action_id,
            "capa_number": a.capa_number,
            "nc_id": a.nc_id,
            "action_type": a.action_type,
            "root_cause_analysis": a.root_cause_analysis,
            "action_plan": a.action_plan,
            "target_completion_date": str(a.target_completion_date),
            "status": a.status,
        }
        for a in actions
    ]
