"""Stock, Warehousing, Serial & Batch Tracking, and Logistics API Router."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.stock import (
    delivery_trip_service,
    pick_packing_service,
    reconciliation_service,
    serial_batch_service,
    stock_entry_service,
    stock_reservation_service,
    variant_service,
)

router = APIRouter(prefix="/stock", tags=["Stock & Logistics"])


# =========================================================================
# Request Schemas
# =========================================================================


class StockEntryItemSchema(BaseModel):
    item_id: uuid.UUID
    s_warehouse_id: uuid.UUID | None = None
    t_warehouse_id: uuid.UUID | None = None
    qty: Decimal
    uom: str = "Nos"
    basic_rate: Decimal = Decimal("0.0000")
    batch_no: str | None = None
    serial_no: str | None = None


class CreateStockEntrySchema(BaseModel):
    entry_number: str = Field(..., min_length=2, max_length=64)
    stock_entry_type: str = "MATERIAL_TRANSFER"  # MATERIAL_RECEIPT, MATERIAL_ISSUE, MATERIAL_TRANSFER, MANUFACTURE, REPACK
    posting_date: date | None = None
    purpose: str | None = None
    from_warehouse_id: uuid.UUID | None = None
    to_warehouse_id: uuid.UUID | None = None
    notes: str | None = None
    items: list[StockEntryItemSchema] = Field(default_factory=list)


class StockReconciliationItemSchema(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    reconciled_qty: Decimal
    reconciled_valuation_rate: Decimal | None = None


class CreateStockReconciliationSchema(BaseModel):
    reconciliation_number: str = Field(..., min_length=2, max_length=64)
    posting_date: date | None = None
    purpose: str = "STOCK_RECONCILIATION"
    expense_account: str = "5200-STOCK-ADJUSTMENT"
    items: list[StockReconciliationItemSchema] = Field(default_factory=list)


class CreateBatchSchema(BaseModel):
    batch_number: str = Field(..., min_length=2, max_length=64)
    item_id: uuid.UUID
    manufacturing_date: date | None = None
    expiry_date: date | None = None
    description: str | None = None


class CreateSerialSchema(BaseModel):
    serial_number: str = Field(..., min_length=2, max_length=128)
    item_id: uuid.UUID
    warehouse_id: uuid.UUID | None = None
    warranty_expiry_date: date | None = None
    purchase_document_type: str | None = None
    purchase_document_id: uuid.UUID | None = None


class UpdateSerialStatusSchema(BaseModel):
    status: str
    warehouse_id: uuid.UUID | None = None
    delivery_document_type: str | None = None
    delivery_document_id: uuid.UUID | None = None


class PickListItemSchema(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_to_pick: Decimal
    picked_qty: Decimal = Decimal("0.0000")
    source_document_type: str | None = None
    source_document_id: uuid.UUID | None = None
    batch_no: str | None = None
    serial_no: str | None = None


class CreatePickListSchema(BaseModel):
    pick_list_number: str = Field(..., min_length=2, max_length=64)
    purpose: str = "DELIVERY"
    customer_id: uuid.UUID | None = None
    notes: str | None = None
    items: list[PickListItemSchema] = Field(default_factory=list)


class UpdatePickedQtySchema(BaseModel):
    picked_qty: Decimal


class PackingSlipItemSchema(BaseModel):
    item_id: uuid.UUID
    qty: Decimal
    net_weight: Decimal = Decimal("0.0000")


class CreatePackingSlipSchema(BaseModel):
    slip_number: str = Field(..., min_length=2, max_length=64)
    delivery_note_id: uuid.UUID | None = None
    from_case_no: int = 1
    to_case_no: int = 1
    net_weight_pkg: Decimal = Decimal("0.0000")
    gross_weight_pkg: Decimal = Decimal("0.0000")
    items: list[PackingSlipItemSchema] = Field(default_factory=list)


class DeliveryStopSchema(BaseModel):
    delivery_note_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    address: str
    stop_sequence: int = 1


class CreateDeliveryTripSchema(BaseModel):
    trip_number: str = Field(..., min_length=2, max_length=64)
    driver_name: str = Field(..., min_length=2, max_length=128)
    vehicle_number: str = Field(..., min_length=2, max_length=64)
    departure_datetime: datetime | None = None
    total_distance_km: Decimal = Decimal("0.00")
    stops: list[DeliveryStopSchema] = Field(default_factory=list)


class CompleteStopSchema(BaseModel):
    customer_signature: str | None = "SIGNED"


class CreateReservationSchema(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    voucher_type: str = "SALES_ORDER"
    voucher_id: uuid.UUID
    reserved_qty: Decimal
    voucher_item_id: uuid.UUID | None = None


class AttributeValueSchema(BaseModel):
    attribute_value: str
    abbr: str | None = None


class CreateAttributeSchema(BaseModel):
    attribute_name: str
    values: list[AttributeValueSchema] = Field(default_factory=list)


class VariantDefinitionSchema(BaseModel):
    item_code: str | None = None
    item_name: str | None = None
    standard_rate: Decimal | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class GenerateVariantsSchema(BaseModel):
    variants: list[VariantDefinitionSchema]


# =========================================================================
# Stock Entries Endpoints
# =========================================================================


@router.post("/entries", status_code=status.HTTP_201_CREATED, summary="Create Stock Entry")
async def create_stock_entry(
    req: CreateStockEntrySchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a draft universal stock movement entry."""
    try:
        return await stock_entry_service.create_stock_entry(
            session=db,
            tenant_id=tenant_id,
            entry_number=req.entry_number,
            stock_entry_type=req.stock_entry_type,
            posting_date=req.posting_date,
            purpose=req.purpose,
            from_warehouse_id=req.from_warehouse_id,
            to_warehouse_id=req.to_warehouse_id,
            notes=req.notes,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/entries", summary="List Stock Entries")
async def list_stock_entries(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    stock_entry_type: str | None = None,
    status: str | None = None,
):
    """Lists stock entries for tenant."""
    return await stock_entry_service.list_stock_entries(db, tenant_id, stock_entry_type, status)


@router.get("/entries/{entry_id}", summary="Get Stock Entry")
async def get_stock_entry(
    entry_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Fetches details of a stock entry."""
    entry = await stock_entry_service.get_stock_entry(db, tenant_id, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock Entry not found.")
    return entry


@router.post("/entries/{entry_id}/submit", summary="Submit Stock Entry")
async def submit_stock_entry(
    entry_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits stock movement, posting StockLedgerEntries, updating StockLevels, and posting GL."""
    try:
        return await stock_entry_service.submit_stock_entry(db, tenant_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/entries/{entry_id}/cancel", summary="Cancel Stock Entry")
async def cancel_stock_entry(
    entry_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Cancels a submitted stock entry."""
    try:
        return await stock_entry_service.cancel_stock_entry(db, tenant_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Stock Reconciliation Endpoints
# =========================================================================


@router.post("/reconciliations", status_code=status.HTTP_201_CREATED, summary="Create Stock Reconciliation")
async def create_stock_reconciliation(
    req: CreateStockReconciliationSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a physical stock reconciliation voucher."""
    try:
        return await reconciliation_service.create_reconciliation(
            session=db,
            tenant_id=tenant_id,
            reconciliation_number=req.reconciliation_number,
            posting_date=req.posting_date,
            purpose=req.purpose,
            expense_account=req.expense_account,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/reconciliations", summary="List Stock Reconciliations")
async def list_stock_reconciliations(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
):
    """Lists stock reconciliations."""
    return await reconciliation_service.list_reconciliations(db, tenant_id, status)


@router.get("/reconciliations/{reconciliation_id}", summary="Get Stock Reconciliation")
async def get_stock_reconciliation(
    reconciliation_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Fetches details of a stock reconciliation."""
    recon = await reconciliation_service.get_reconciliation(db, tenant_id, reconciliation_id)
    if not recon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found.")
    return recon


@router.post("/reconciliations/{reconciliation_id}/submit", summary="Submit Stock Reconciliation")
async def submit_stock_reconciliation(
    reconciliation_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits stock reconciliation, adjusting inventory quantities and posting variance GL entries."""
    try:
        return await reconciliation_service.submit_reconciliation(db, tenant_id, reconciliation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Serial & Batch Endpoints
# =========================================================================


@router.post("/batches", status_code=status.HTTP_201_CREATED, summary="Create Batch Lot")
async def create_batch(
    req: CreateBatchSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Registers a new batch lot."""
    try:
        return await serial_batch_service.create_batch(
            session=db,
            tenant_id=tenant_id,
            batch_number=req.batch_number,
            item_id=req.item_id,
            manufacturing_date=req.manufacturing_date,
            expiry_date=req.expiry_date,
            description=req.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/batches", summary="List Batches")
async def list_batches(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    item_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists batches with expiration status."""
    return await serial_batch_service.list_batches(db, tenant_id, item_id, status)


@router.post("/serials", status_code=status.HTTP_201_CREATED, summary="Create Serial Number")
async def create_serial(
    req: CreateSerialSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Registers an individual unit serial number."""
    try:
        return await serial_batch_service.create_serial_number(
            session=db,
            tenant_id=tenant_id,
            serial_number=req.serial_number,
            item_id=req.item_id,
            warehouse_id=req.warehouse_id,
            warranty_expiry_date=req.warranty_expiry_date,
            purchase_document_type=req.purchase_document_type,
            purchase_document_id=req.purchase_document_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/serials", summary="List Serial Numbers")
async def list_serials(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists unit serial numbers."""
    return await serial_batch_service.list_serial_numbers(db, tenant_id, item_id, warehouse_id, status)


@router.post("/serials/{serial_number}/status", summary="Update Serial Status")
async def update_serial_status(
    serial_number: str,
    req: UpdateSerialStatusSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Updates unit serial status (ACTIVE, DELIVERED, EXPIRED)."""
    try:
        return await serial_batch_service.update_serial_status(
            session=db,
            tenant_id=tenant_id,
            serial_number=serial_number,
            new_status=req.status,
            warehouse_id=req.warehouse_id,
            delivery_document_type=req.delivery_document_type,
            delivery_document_id=req.delivery_document_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Pick Lists Endpoints
# =========================================================================


@router.post("/pick-lists", status_code=status.HTTP_201_CREATED, summary="Create Pick List")
async def create_pick_list(
    req: CreatePickListSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a warehouse pick list."""
    try:
        return await pick_packing_service.create_pick_list(
            session=db,
            tenant_id=tenant_id,
            pick_list_number=req.pick_list_number,
            purpose=req.purpose,
            customer_id=req.customer_id,
            notes=req.notes,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pick-lists", summary="List Pick Lists")
async def list_pick_lists(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
):
    """Lists warehouse pick lists."""
    return await pick_packing_service.list_pick_lists(db, tenant_id, status)


@router.get("/pick-lists/{pick_list_id}", summary="Get Pick List")
async def get_pick_list(
    pick_list_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets pick list details."""
    pl = await pick_packing_service.get_pick_list(db, tenant_id, pick_list_id)
    if not pl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick List not found.")
    return pl


@router.post("/pick-lists/{pick_list_id}/items/{pick_item_id}/picked", summary="Update Picked Quantity")
async def update_picked_qty(
    pick_list_id: uuid.UUID,
    pick_item_id: uuid.UUID,
    req: UpdatePickedQtySchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Updates picked quantity for a pick list item."""
    try:
        return await pick_packing_service.update_picked_qty(
            db, tenant_id, pick_list_id, pick_item_id, req.picked_qty
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/pick-lists/{pick_list_id}/complete", summary="Complete Pick List")
async def complete_pick_list(
    pick_list_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Marks pick list as COMPLETED."""
    try:
        return await pick_packing_service.complete_pick_list(db, tenant_id, pick_list_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Packing Slips Endpoints
# =========================================================================


@router.post("/packing-slips", status_code=status.HTTP_201_CREATED, summary="Create Packing Slip")
async def create_packing_slip(
    req: CreatePackingSlipSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a carton/crate packing slip manifest."""
    try:
        return await pick_packing_service.create_packing_slip(
            session=db,
            tenant_id=tenant_id,
            slip_number=req.slip_number,
            delivery_note_id=req.delivery_note_id,
            from_case_no=req.from_case_no,
            to_case_no=req.to_case_no,
            net_weight_pkg=req.net_weight_pkg,
            gross_weight_pkg=req.gross_weight_pkg,
            items=[i.model_dump() for i in req.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/packing-slips", summary="List Packing Slips")
async def list_packing_slips(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    delivery_note_id: uuid.UUID | None = None,
):
    """Lists packing slips."""
    return await pick_packing_service.list_packing_slips(db, tenant_id, delivery_note_id)


@router.post("/packing-slips/{packing_slip_id}/submit", summary="Submit Packing Slip")
async def submit_packing_slip(
    packing_slip_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Submits packing slip manifest."""
    try:
        return await pick_packing_service.submit_packing_slip(db, tenant_id, packing_slip_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Delivery Trips Endpoints
# =========================================================================


@router.post("/delivery-trips", status_code=status.HTTP_201_CREATED, summary="Create Delivery Trip")
async def create_delivery_trip(
    req: CreateDeliveryTripSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Plans a multi-stop vehicle delivery route."""
    try:
        return await delivery_trip_service.create_delivery_trip(
            session=db,
            tenant_id=tenant_id,
            trip_number=req.trip_number,
            driver_name=req.driver_name,
            vehicle_number=req.vehicle_number,
            departure_datetime=req.departure_datetime,
            total_distance_km=req.total_distance_km,
            stops=[s.model_dump() for s in req.stops],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/delivery-trips", summary="List Delivery Trips")
async def list_delivery_trips(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: str | None = None,
):
    """Lists delivery trips."""
    return await delivery_trip_service.list_delivery_trips(db, tenant_id, status)


@router.get("/delivery-trips/{trip_id}", summary="Get Delivery Trip")
async def get_delivery_trip(
    trip_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Gets delivery trip route details."""
    trip = await delivery_trip_service.get_delivery_trip(db, tenant_id, trip_id)
    if not trip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery Trip not found.")
    return trip


@router.post("/delivery-trips/{trip_id}/dispatch", summary="Dispatch Delivery Trip")
async def dispatch_delivery_trip(
    trip_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Dispatches delivery vehicle (IN_TRANSIT)."""
    try:
        return await delivery_trip_service.dispatch_trip(db, tenant_id, trip_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/delivery-trips/{trip_id}/stops/{stop_id}/complete", summary="Complete Delivery Stop")
async def complete_delivery_stop(
    trip_id: uuid.UUID,
    stop_id: uuid.UUID,
    req: CompleteStopSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Marks an individual stop as DELIVERED with proof of delivery."""
    try:
        return await delivery_trip_service.complete_stop(
            db, tenant_id, trip_id, stop_id, req.customer_signature
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/delivery-trips/{trip_id}/complete", summary="Complete Delivery Trip")
async def complete_delivery_trip(
    trip_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Marks the entire delivery trip as COMPLETED."""
    try:
        return await delivery_trip_service.complete_trip(db, tenant_id, trip_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Stock Reservations Endpoints
# =========================================================================


@router.post("/reservations", status_code=status.HTTP_201_CREATED, summary="Create Stock Reservation")
async def create_stock_reservation(
    req: CreateReservationSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Locks inventory against a Sales Order or Material Demand."""
    try:
        return await stock_reservation_service.create_reservation(
            session=db,
            tenant_id=tenant_id,
            item_id=req.item_id,
            warehouse_id=req.warehouse_id,
            voucher_type=req.voucher_type,
            voucher_id=req.voucher_id,
            reserved_qty=req.reserved_qty,
            voucher_item_id=req.voucher_item_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/reservations", summary="List Stock Reservations")
async def list_stock_reservations(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status: str | None = None,
):
    """Lists active inventory reservations."""
    return await stock_reservation_service.list_reservations(db, tenant_id, item_id, warehouse_id, status)


@router.post("/reservations/{reservation_id}/cancel", summary="Cancel Stock Reservation")
async def cancel_stock_reservation(
    reservation_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Cancels reservation and restores available stock."""
    try:
        return await stock_reservation_service.cancel_reservation(db, tenant_id, reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =========================================================================
# Item Attributes & Variants Endpoints
# =========================================================================


@router.post("/attributes", status_code=status.HTTP_201_CREATED, summary="Create Item Attribute")
async def create_item_attribute(
    req: CreateAttributeSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a variant attribute specification (e.g. Size, Color)."""
    try:
        return await variant_service.create_attribute(
            session=db,
            tenant_id=tenant_id,
            attribute_name=req.attribute_name,
            values=[v.model_dump() for v in req.values],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/attributes", summary="List Item Attributes")
async def list_item_attributes(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Lists variant attributes and their allowed values."""
    return await variant_service.list_attributes(db, tenant_id)


@router.post("/items/{template_item_id}/variants", status_code=status.HTTP_201_CREATED, summary="Generate Item Variants")
async def generate_item_variants(
    template_item_id: uuid.UUID,
    req: GenerateVariantsSchema,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Generates concrete SKU items from a template product."""
    try:
        return await variant_service.generate_item_variants(
            session=db,
            tenant_id=tenant_id,
            template_item_id=template_item_id,
            variant_definitions=[v.model_dump() for v in req.variants],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/items/{template_item_id}/variants", summary="List Variants of Template Item")
async def list_variants_of_item(
    template_item_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Lists all generated variants for a template product."""
    return await variant_service.list_variants_of_item(db, tenant_id, template_item_id)
