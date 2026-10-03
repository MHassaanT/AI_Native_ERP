"""Procurement, Sourcing, Landed Costs, and Subcontracting API Router."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from erp.workflows.procurement import (
    blanket_order_service,
    landed_cost_service,
    requisition_service,
    sourcing_service,
    subcontracting_service,
    supplier_scorecard_service,
)

router = APIRouter(prefix="/procurement", tags=["Procurement & Sourcing"])


# =========================================================================
# Request Schemas
# =========================================================================


class MaterialRequestItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    target_warehouse_id: uuid.UUID | None = None
    uom: str = "Nos"


class CreateMaterialRequestSchema(BaseModel):
    mr_number: str = Field(..., min_length=2, max_length=64)
    material_request_type: str = "PURCHASE"  # PURCHASE, MATERIAL_TRANSFER, MATERIAL_ISSUE, MANUFACTURE
    schedule_date: date | None = None
    notes: str | None = None
    items: list[MaterialRequestItemSchema] = Field(default_factory=list)


class ConvertMRToPOSchema(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    items: list[dict[str, Any]] | None = None


class RFQItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    required_date: date | None = None


class CreateRFQSchema(BaseModel):
    rfq_number: str = Field(..., min_length=2, max_length=64)
    transaction_date: date | None = None
    notes: str | None = None
    supplier_ids: list[uuid.UUID] = Field(default_factory=list)
    items: list[RFQItemSchema] = Field(default_factory=list)


class SupplierQuoteItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal = Decimal("0.00")
    lead_time_days: int = 7


class CreateSupplierQuoteSchema(BaseModel):
    quotation_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    rfq_id: uuid.UUID | None = None
    quotation_date: date | None = None
    valid_until: date | None = None
    currency: str = "USD"
    lead_time_days: int = 7
    payment_terms: str | None = None
    items: list[SupplierQuoteItemSchema] = Field(default_factory=list)


class AwardQuoteSchema(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)


class BlanketOrderItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal


class CreateBlanketOrderSchema(BaseModel):
    order_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    from_date: date
    to_date: date
    items: list[BlanketOrderItemSchema]


class BlanketOrderDrawdownItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal


class BlanketOrderDrawdownSchema(BaseModel):
    po_number: str = Field(..., min_length=2, max_length=64)
    order_date: date | None = None
    items: list[BlanketOrderDrawdownItemSchema]


class LandedCostChargeSchema(BaseModel):
    expense_account: str = "5100-FREIGHT-CUSTOMS-CLEARING"
    description: str
    amount: Decimal


class CreateLCVSchema(BaseModel):
    voucher_number: str = Field(..., min_length=2, max_length=64)
    grn_ids: list[uuid.UUID]
    distribute_charges_based_on: str = "VALUATION"  # VALUATION, QUANTITY
    posting_date: date | None = None
    company: str = "Corporate"
    notes: str | None = None
    taxes_and_charges: list[LandedCostChargeSchema]


class CalculateScorecardSchema(BaseModel):
    supplier_id: uuid.UUID
    period_start: date
    period_end: date
    evaluation_period: str = "MONTHLY"


class SubcontractingOrderItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal = Decimal("0.0000")


class SubcontractingSuppliedItemSchema(BaseModel):
    raw_item_id: uuid.UUID
    required_qty: Decimal
    source_warehouse_id: uuid.UUID | None = None
    supplier_warehouse_id: uuid.UUID | None = None


class CreateSubcontractingOrderSchema(BaseModel):
    sco_number: str = Field(..., min_length=2, max_length=64)
    supplier_id: uuid.UUID
    order_date: date | None = None
    service_cost: Decimal = Decimal("0.0000")
    po_id: uuid.UUID | None = None
    notes: str | None = None
    finished_items: list[SubcontractingOrderItemSchema] = Field(default_factory=list)
    supplied_items: list[SubcontractingSuppliedItemSchema] = Field(default_factory=list)


class TransferMaterialsItemSchema(BaseModel):
    raw_item_id: uuid.UUID
    quantity: Decimal
    source_warehouse_id: uuid.UUID
    supplier_warehouse_id: uuid.UUID


class TransferMaterialsSchema(BaseModel):
    transfers: list[TransferMaterialsItemSchema]


class SubcontractingReceiptItemSchema(BaseModel):
    item_id: uuid.UUID
    quantity_received: Decimal
    service_rate: Decimal = Decimal("0.0000")


class CreateSubcontractingReceiptSchema(BaseModel):
    scr_number: str = Field(..., min_length=2, max_length=64)
    sco_id: uuid.UUID
    target_warehouse_id: uuid.UUID
    posting_date: date | None = None
    finished_items: list[SubcontractingReceiptItemSchema]


class InspectGRNItemSchema(BaseModel):
    grn_item_id: uuid.UUID
    quantity_accepted: Decimal
    quantity_rejected: Decimal = Decimal("0.0000")
    rejected_warehouse_id: uuid.UUID | None = None


class InspectGRNSchema(BaseModel):
    items: list[InspectGRNItemSchema]


# =========================================================================
# 0. Warehouses Master Lookup
# =========================================================================


@router.get("/warehouses", summary="List Warehouses for Procurement")
async def list_procurement_warehouses(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Lists warehouses for target receiving and subcontractor sourcing."""
    stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.is_active == True).order_by(Warehouse.warehouse_name)
    return (await db.execute(stmt)).scalars().all()


# =========================================================================
# 1. Material Requests / Requisitions
# =========================================================================


@router.get("/material-requests", summary="List Material Requests")
async def list_material_requests(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
    material_request_type: str | None = None,
):
    """Lists material requests for tenant."""
    return await requisition_service.list_material_requests(
        session=db,
        tenant_id=tenant_id,
        status=status,
        material_request_type=material_request_type,
    )


@router.post("/material-requests", status_code=status.HTTP_201_CREATED, summary="Create Material Request")
async def create_material_request(
    req: CreateMaterialRequestSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a new Material Request (Requisition)."""
    try:
        mr = await requisition_service.create_material_request(
            session=db,
            tenant_id=tenant_id,
            mr_number=req.mr_number,
            material_request_type=req.material_request_type,
            schedule_date=req.schedule_date,
            notes=req.notes,
            items=[i.model_dump() for i in req.items],
        )
        return mr
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/material-requests/{mr_id}", summary="Get Material Request")
async def get_material_request(
    mr_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Fetches Material Request details."""
    mr = await requisition_service.get_material_request(db, tenant_id, mr_id)
    if not mr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material Request not found.")
    return mr


@router.post("/material-requests/{mr_id}/submit", summary="Submit Material Request")
async def submit_material_request(
    mr_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits Material Request."""
    try:
        return await requisition_service.submit_material_request(db, tenant_id, mr_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/material-requests/{mr_id}/cancel", summary="Cancel Material Request")
async def cancel_material_request(
    mr_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Cancels Material Request."""
    try:
        return await requisition_service.cancel_material_request(db, tenant_id, mr_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/material-requests/{mr_id}/create-po", summary="Generate PO from Material Request")
async def create_po_from_material_request(
    mr_id: uuid.UUID,
    req: ConvertMRToPOSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Converts pending items in a submitted Material Request into a Purchase Order."""
    try:
        po = await requisition_service.create_po_from_material_request(
            session=db,
            tenant_id=tenant_id,
            mr_id=mr_id,
            supplier_id=req.supplier_id,
            po_number=req.po_number,
            items_to_order=req.items,
        )
        return po
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/replenishment/check", summary="Check Reorder Replenishment")
async def check_reorder_replenishment(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Scans inventory levels vs safety thresholds and creates automated Material Requests."""
    created = await requisition_service.check_reorder_replenishment(db, tenant_id)
    return {"message": f"Generated {len(created)} automated replenishment requisition(s).", "requests": created}


# =========================================================================
# 2. RFQ & Strategic Sourcing & Quote Comparison Matrix
# =========================================================================


@router.get("/rfqs", summary="List RFQs")
async def list_rfqs(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
):
    """Lists Requests for Quotations."""
    return await sourcing_service.list_rfqs(db, tenant_id, status=status)


@router.post("/rfqs", status_code=status.HTTP_201_CREATED, summary="Create RFQ")
async def create_rfq(
    req: CreateRFQSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a Request for Quotation."""
    try:
        return await sourcing_service.create_rfq(
            session=db,
            tenant_id=tenant_id,
            rfq_number=req.rfq_number,
            transaction_date=req.transaction_date,
            notes=req.notes,
            supplier_ids=req.supplier_ids,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/rfqs/{rfq_id}", summary="Get RFQ")
async def get_rfq(
    rfq_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets RFQ details."""
    rfq = await sourcing_service.get_rfq(db, tenant_id, rfq_id)
    if not rfq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found.")
    return rfq


@router.post("/rfqs/{rfq_id}/send", summary="Send RFQ to Suppliers")
async def send_rfq(
    rfq_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Marks RFQ as SENT."""
    try:
        return await sourcing_service.send_rfq(db, tenant_id, rfq_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/rfqs/{rfq_id}/comparison-matrix", summary="Get Side-by-Side Quote Comparison Matrix")
async def get_quote_comparison_matrix(
    rfq_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Computes side-by-side bid comparison matrix across suppliers."""
    try:
        return await sourcing_service.get_quote_comparison_matrix(db, tenant_id, rfq_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/supplier-quotations", summary="List Supplier Quotations")
async def list_supplier_quotations(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    rfq_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists vendor quotations."""
    return await sourcing_service.list_supplier_quotations(
        session=db,
        tenant_id=tenant_id,
        rfq_id=rfq_id,
        supplier_id=supplier_id,
        status=status,
    )


@router.post("/supplier-quotations", status_code=status.HTTP_201_CREATED, summary="Create Supplier Quotation")
async def create_supplier_quotation(
    req: CreateSupplierQuoteSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits vendor quotation."""
    try:
        return await sourcing_service.create_supplier_quotation(
            session=db,
            tenant_id=tenant_id,
            quotation_number=req.quotation_number,
            supplier_id=req.supplier_id,
            rfq_id=req.rfq_id,
            quotation_date=req.quotation_date,
            valid_until=req.valid_until,
            currency=req.currency,
            lead_time_days=req.lead_time_days,
            payment_terms=req.payment_terms,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/supplier-quotations/{sq_id}", summary="Get Supplier Quotation")
async def get_supplier_quotation(
    sq_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets quotation details."""
    quote = await sourcing_service.get_supplier_quotation(db, tenant_id, sq_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found.")
    return quote


@router.post("/supplier-quotations/{sq_id}/award", summary="Award Quotation to Purchase Order")
async def award_quotation(
    sq_id: uuid.UUID,
    req: AwardQuoteSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """1-Click Awards quotation, rejects competitors, and generates Purchase Order."""
    try:
        return await sourcing_service.award_quotation_to_po(
            session=db,
            tenant_id=tenant_id,
            sq_id=sq_id,
            po_number=req.po_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# 3. Blanket Orders
# =========================================================================


@router.get("/blanket-orders", summary="List Blanket Orders")
async def list_blanket_orders(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    supplier_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists long-term blanket contracts."""
    return await blanket_order_service.list_blanket_orders(
        session=db,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        status=status,
    )


@router.post("/blanket-orders", status_code=status.HTTP_201_CREATED, summary="Create Blanket Order")
async def create_blanket_order(
    req: CreateBlanketOrderSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a long-term Blanket Order."""
    try:
        return await blanket_order_service.create_blanket_order(
            session=db,
            tenant_id=tenant_id,
            order_number=req.order_number,
            supplier_id=req.supplier_id,
            from_date=req.from_date,
            to_date=req.to_date,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/blanket-orders/{bo_id}", summary="Get Blanket Order")
async def get_blanket_order(
    bo_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets Blanket Order details."""
    bo = await blanket_order_service.get_blanket_order(db, tenant_id, bo_id)
    if not bo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blanket Order not found.")
    return bo


@router.post("/blanket-orders/{bo_id}/create-po", summary="Drawdown PO against Blanket Order")
async def create_po_from_blanket_order(
    bo_id: uuid.UUID,
    req: BlanketOrderDrawdownSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Draws down against a blanket order with contracted pricing."""
    try:
        return await blanket_order_service.create_po_from_blanket_order(
            session=db,
            tenant_id=tenant_id,
            blanket_order_id=bo_id,
            po_number=req.po_number,
            item_drawdowns=[i.model_dump() for i in req.items],
            order_date=req.order_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# 4. Landed Cost Vouchers
# =========================================================================


@router.get("/landed-cost-vouchers", summary="List Landed Cost Vouchers")
async def list_landed_cost_vouchers(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
):
    """Lists Landed Cost Vouchers."""
    return await landed_cost_service.list_landed_cost_vouchers(
        session=db,
        tenant_id=tenant_id,
        status=status,
    )


@router.post("/landed-cost-vouchers", status_code=status.HTTP_201_CREATED, summary="Create Landed Cost Voucher")
async def create_landed_cost_voucher(
    req: CreateLCVSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a Landed Cost Voucher and apportions freight/customs charges."""
    try:
        return await landed_cost_service.create_landed_cost_voucher(
            session=db,
            tenant_id=tenant_id,
            voucher_number=req.voucher_number,
            grn_ids=req.grn_ids,
            distribute_charges_based_on=req.distribute_charges_based_on,
            posting_date=req.posting_date,
            company=req.company,
            notes=req.notes,
            taxes_and_charges=[c.model_dump() for c in req.taxes_and_charges],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/landed-cost-vouchers/{lcv_id}", summary="Get Landed Cost Voucher")
async def get_landed_cost_voucher(
    lcv_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets Landed Cost Voucher details."""
    lcv = await landed_cost_service.get_landed_cost_voucher(db, tenant_id, lcv_id)
    if not lcv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landed Cost Voucher not found.")
    return lcv


@router.post("/landed-cost-vouchers/{lcv_id}/submit", summary="Submit Landed Cost Voucher")
async def submit_landed_cost_voucher(
    lcv_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits Landed Cost Voucher, capitalizes charges to inventory, and posts GL entries."""
    try:
        return await landed_cost_service.submit_landed_cost_voucher(db, tenant_id, lcv_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# 5. Supplier Performance Scorecards & Leaderboard
# =========================================================================


@router.get("/scorecards", summary="List Supplier Scorecards")
async def list_scorecards(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    supplier_id: uuid.UUID | None = None,
    standing: str | None = None,
):
    """Lists vendor scorecards."""
    return await supplier_scorecard_service.list_scorecards(
        session=db,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        standing=standing,
    )


@router.post("/scorecards/calculate", status_code=status.HTTP_201_CREATED, summary="Calculate Supplier Scorecard")
async def calculate_supplier_scorecard(
    req: CalculateScorecardSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Calculates OTIF, Quality, and Price Variance metrics and records a Scorecard."""
    try:
        return await supplier_scorecard_service.calculate_and_generate_scorecard(
            session=db,
            tenant_id=tenant_id,
            supplier_id=req.supplier_id,
            period_start=req.period_start,
            period_end=req.period_end,
            evaluation_period=req.evaluation_period,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/scorecards/{scorecard_id}", summary="Get Supplier Scorecard")
async def get_supplier_scorecard(
    scorecard_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets scorecard details."""
    sc = await supplier_scorecard_service.get_scorecard(db, tenant_id, scorecard_id)
    if not sc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scorecard not found.")
    return sc


@router.get("/suppliers/leaderboard", summary="Get Supplier Performance Leaderboard")
async def get_supplier_leaderboard(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Returns ranked supplier leaderboard with OTIF, Quality, and Tier standing."""
    return await supplier_scorecard_service.get_supplier_leaderboard(db, tenant_id)


# =========================================================================
# 6. Subcontracting
# =========================================================================


@router.get("/subcontracting-orders", summary="List Subcontracting Orders")
async def list_subcontracting_orders(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    supplier_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists subcontracting orders."""
    return await subcontracting_service.list_subcontracting_orders(
        session=db,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        status=status,
    )


@router.post("/subcontracting-orders", status_code=status.HTTP_201_CREATED, summary="Create Subcontracting Order")
async def create_subcontracting_order(
    req: CreateSubcontractingOrderSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a Subcontracting Order."""
    try:
        return await subcontracting_service.create_subcontracting_order(
            session=db,
            tenant_id=tenant_id,
            sco_number=req.sco_number,
            supplier_id=req.supplier_id,
            order_date=req.order_date,
            service_cost=req.service_cost,
            po_id=req.po_id,
            notes=req.notes,
            finished_items=[i.model_dump() for i in req.finished_items],
            supplied_items=[i.model_dump() for i in req.supplied_items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/subcontracting-orders/{sco_id}", summary="Get Subcontracting Order")
async def get_subcontracting_order(
    sco_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets Subcontracting Order details."""
    sco = await subcontracting_service.get_subcontracting_order(db, tenant_id, sco_id)
    if not sco:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcontracting Order not found.")
    return sco


@router.post("/subcontracting-orders/{sco_id}/submit", summary="Submit Subcontracting Order")
async def submit_subcontracting_order(
    sco_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits Subcontracting Order."""
    try:
        return await subcontracting_service.submit_subcontracting_order(db, tenant_id, sco_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/subcontracting-orders/{sco_id}/transfer-materials", summary="Transfer Materials to Subcontractor")
async def transfer_subcontracting_materials(
    sco_id: uuid.UUID,
    req: TransferMaterialsSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Issues raw components from internal warehouse to subcontractor warehouse."""
    try:
        return await subcontracting_service.transfer_subcontracting_materials(
            session=db,
            tenant_id=tenant_id,
            sco_id=sco_id,
            transfers=[t.model_dump() for t in req.transfers],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/subcontracting-receipts", summary="List Subcontracting Receipts")
async def list_subcontracting_receipts(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    sco_id: uuid.UUID | None = None,
):
    """Lists Subcontracting Receipts."""
    return await subcontracting_service.list_subcontracting_receipts(
        session=db,
        tenant_id=tenant_id,
        sco_id=sco_id,
    )


@router.post("/subcontracting-receipts", status_code=status.HTTP_201_CREATED, summary="Receive Subcontracted Finished Goods")
async def create_subcontracting_receipt(
    req: CreateSubcontractingReceiptSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Receives finished goods into inventory and consumes raw materials from vendor warehouse."""
    try:
        return await subcontracting_service.receive_subcontracting_receipt(
            session=db,
            tenant_id=tenant_id,
            scr_number=req.scr_number,
            sco_id=req.sco_id,
            target_warehouse_id=req.target_warehouse_id,
            finished_items_received=[i.model_dump() for i in req.finished_items],
            posting_date=req.posting_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/subcontracting-receipts/{scr_id}", summary="Get Subcontracting Receipt")
async def get_subcontracting_receipt(
    scr_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets Subcontracting Receipt details."""
    scr = await subcontracting_service.get_subcontracting_receipt(db, tenant_id, scr_id)
    if not scr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcontracting Receipt not found.")
    return scr


# =========================================================================
# 7. GRN Inspection & Acceptance / Quarantine
# =========================================================================


@router.post("/grn/{grn_id}/inspect", summary="Perform Quality Inspection on GRN")
async def inspect_grn(
    grn_id: uuid.UUID,
    req: InspectGRNSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Inspects received goods in a GRN, splitting accepted and rejected quantities."""
    grn_stmt = (
        select(GoodsReceiptNote)
        .options(selectinload(GoodsReceiptNote.items))
        .where(
            GoodsReceiptNote.tenant_id == tenant_id,
            GoodsReceiptNote.grn_id == grn_id,
        )
    )
    grn = (await db.execute(grn_stmt)).scalar_one_or_none()
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")

    items_by_id = {item.grn_item_id: item for item in grn.items}

    for insp in req.items:
        grn_item = items_by_id.get(insp.grn_item_id)
        if not grn_item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item {insp.grn_item_id} not found in GRN {grn.grn_number}",
            )

        if (insp.quantity_accepted + insp.quantity_rejected) > grn_item.quantity_received:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Accepted ({insp.quantity_accepted}) + Rejected ({insp.quantity_rejected}) cannot exceed received quantity ({grn_item.quantity_received}).",
            )

        grn_item.quantity_accepted = insp.quantity_accepted
        grn_item.quantity_rejected = insp.quantity_rejected
        if insp.rejected_warehouse_id:
            grn_item.rejected_warehouse_id = insp.rejected_warehouse_id

            # Move rejected stock into quarantine warehouse if rejected quantity > 0
            if insp.quantity_rejected > Decimal("0.0000"):
                rej_stk = (
                    await db.execute(
                        select(StockLevel).where(
                            StockLevel.tenant_id == tenant_id,
                            StockLevel.item_id == grn_item.item_id,
                            StockLevel.warehouse_id == insp.rejected_warehouse_id,
                        )
                    )
                ).scalar_one_or_none()

                rate = grn_item.unit_price or Decimal("0.0000")
                if rej_stk:
                    rej_stk.current_qty += insp.quantity_rejected
                    rej_stk.available_qty = rej_stk.current_qty - rej_stk.reserved_qty
                    qty_after = rej_stk.current_qty
                else:
                    rej_stk = StockLevel(
                        tenant_id=tenant_id,
                        item_id=grn_item.item_id,
                        warehouse_id=insp.rejected_warehouse_id,
                        current_qty=insp.quantity_rejected,
                        reserved_qty=Decimal("0.0000"),
                        available_qty=insp.quantity_rejected,
                        valuation_rate=rate,
                    )
                    db.add(rej_stk)
                    qty_after = insp.quantity_rejected

                db.add(
                    StockLedgerEntry(
                        tenant_id=tenant_id,
                        posting_datetime=datetime.now(),
                        item_id=grn_item.item_id,
                        warehouse_id=insp.rejected_warehouse_id,
                        actual_qty=insp.quantity_rejected,
                        qty_after_transaction=qty_after,
                        incoming_rate=rate,
                        valuation_rate=rate,
                        source_document_type="GRN_QUARANTINE_REJECT",
                        source_document_id=grn.grn_id,
                    )
                )

    await db.flush()
    return {"message": "GRN inspection completed successfully.", "grn_id": str(grn.grn_id)}
