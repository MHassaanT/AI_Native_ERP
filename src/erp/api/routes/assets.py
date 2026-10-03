"""Fixed Assets Lifecycle, Depreciation Schedules, Asset Movements & Scrapping API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.assets import asset_service

router = APIRouter(prefix="/assets", tags=["Fixed Assets & Depreciation"])


# Schemas
class CreateCategorySchema(BaseModel):
    category_name: str
    depreciation_method: str = "STRAIGHT_LINE"
    total_number_of_depreciations: int = 36
    frequency_in_months: int = 1
    fixed_asset_account: str = "1500-FIXED-ASSETS"
    accumulated_depreciation_account: str = "1550-ACCUMULATED-DEPRECIATION"
    depreciation_expense_account: str = "5200-DEP-MACHINERY"


class CreateLocationSchema(BaseModel):
    location_name: str
    parent_location_id: Optional[uuid.UUID] = None


class CreateAssetSchema(BaseModel):
    asset_code: str
    asset_name: str
    asset_category_id: uuid.UUID
    purchase_date: date
    available_for_use_date: date
    gross_purchase_amount: Decimal
    salvage_value: Decimal = Decimal("0.0000")
    location_id: Optional[uuid.UUID] = None
    custodian_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    auto_generate_schedule: bool = True


class AssetMovementSchema(BaseModel):
    to_location_id: Optional[uuid.UUID] = None
    to_custodian_id: Optional[uuid.UUID] = None
    movement_date: Optional[date] = None
    purpose: Optional[str] = None


class AssetRepairSchema(BaseModel):
    repair_cost: Decimal
    repair_description: str
    repair_date: Optional[date] = None
    is_capitalized: bool = False


class AssetScrapSchema(BaseModel):
    disposal_date: Optional[date] = None
    notes: Optional[str] = None


# Endpoints
@router.post("/categories", status_code=status.HTTP_201_CREATED, summary="Create Asset Category")
async def create_category(req: CreateCategorySchema, tenant_id: TenantIdDep, db: DbSessionDep):
    cat = await asset_service.create_category(
        session=db,
        tenant_id=tenant_id,
        category_name=req.category_name,
        depreciation_method=req.depreciation_method,
        total_number_of_depreciations=req.total_number_of_depreciations,
        frequency_in_months=req.frequency_in_months,
        fixed_asset_account=req.fixed_asset_account,
        accumulated_depreciation_account=req.accumulated_depreciation_account,
        depreciation_expense_account=req.depreciation_expense_account,
    )
    return {
        "category_id": cat.category_id,
        "category_name": cat.category_name,
        "depreciation_method": cat.depreciation_method,
        "total_number_of_depreciations": cat.total_number_of_depreciations,
    }


@router.get("/categories", summary="List Asset Categories")
async def list_categories(tenant_id: TenantIdDep, db: DbSessionDep):
    cats = await asset_service.list_categories(db, tenant_id)
    return [
        {
            "category_id": c.category_id,
            "category_name": c.category_name,
            "depreciation_method": c.depreciation_method,
            "total_number_of_depreciations": c.total_number_of_depreciations,
            "frequency_in_months": c.frequency_in_months,
            "fixed_asset_account": c.fixed_asset_account,
            "accumulated_depreciation_account": c.accumulated_depreciation_account,
            "depreciation_expense_account": c.depreciation_expense_account,
        }
        for c in cats
    ]


@router.post("/locations", status_code=status.HTTP_201_CREATED, summary="Create Asset Location")
async def create_location(req: CreateLocationSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    loc = await asset_service.create_location(
        session=db,
        tenant_id=tenant_id,
        location_name=req.location_name,
        parent_location_id=req.parent_location_id,
    )
    return {"location_id": loc.location_id, "location_name": loc.location_name}


@router.get("/locations", summary="List Asset Locations")
async def list_locations(tenant_id: TenantIdDep, db: DbSessionDep):
    locs = await asset_service.list_locations(db, tenant_id)
    return [{"location_id": l.location_id, "location_name": l.location_name, "parent_location_id": l.parent_location_id} for l in locs]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register Fixed Asset")
async def create_asset(req: CreateAssetSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        asset = await asset_service.create_asset(
            session=db,
            tenant_id=tenant_id,
            asset_code=req.asset_code,
            asset_name=req.asset_name,
            asset_category_id=req.asset_category_id,
            purchase_date=req.purchase_date,
            available_for_use_date=req.available_for_use_date,
            gross_purchase_amount=req.gross_purchase_amount,
            salvage_value=req.salvage_value,
            location_id=req.location_id,
            custodian_id=req.custodian_id,
            notes=req.notes,
            auto_generate_schedule=req.auto_generate_schedule,
        )
        return {
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "asset_name": asset.asset_name,
            "gross_purchase_amount": float(asset.gross_purchase_amount),
            "current_book_value": float(asset.current_book_value),
            "status": asset.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", summary="List Fixed Assets")
async def list_assets(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    status: Optional[str] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
):
    assets = await asset_service.list_assets(db, tenant_id, status=status, category_id=category_id)
    return [
        {
            "asset_id": a.asset_id,
            "asset_code": a.asset_code,
            "asset_name": a.asset_name,
            "category_name": a.category.category_name if a.category else None,
            "gross_purchase_amount": float(a.gross_purchase_amount),
            "current_book_value": float(a.current_book_value),
            "accumulated_depreciation": float(a.accumulated_depreciation),
            "status": a.status,
            "purchase_date": str(a.purchase_date),
            "available_for_use_date": str(a.available_for_use_date),
        }
        for a in assets
    ]


@router.get("/{asset_id}", summary="Get Asset Details with Schedule")
async def get_asset(asset_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    asset = await asset_service.get_asset(db, tenant_id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        "asset_id": asset.asset_id,
        "asset_code": asset.asset_code,
        "asset_name": asset.asset_name,
        "category_id": asset.asset_category_id,
        "category_name": asset.category.category_name if asset.category else None,
        "gross_purchase_amount": float(asset.gross_purchase_amount),
        "salvage_value": float(asset.salvage_value),
        "current_book_value": float(asset.current_book_value),
        "accumulated_depreciation": float(asset.accumulated_depreciation),
        "status": asset.status,
        "purchase_date": str(asset.purchase_date),
        "available_for_use_date": str(asset.available_for_use_date),
        "schedules": [
            {
                "schedule_id": s.schedule_id,
                "schedule_date": str(s.schedule_date),
                "depreciation_amount": float(s.depreciation_amount),
                "accumulated_depreciation": float(s.accumulated_depreciation),
                "book_value_after_depreciation": float(s.book_value_after_depreciation),
                "is_posted": s.is_posted,
                "journal_entry_id": s.journal_entry_id,
            }
            for s in asset.schedules
        ],
        "movements": [
            {
                "movement_id": m.movement_id,
                "movement_date": str(m.movement_date),
                "purpose": m.purpose,
                "from_location_id": m.from_location_id,
                "to_location_id": m.to_location_id,
            }
            for m in asset.movements
        ],
        "repairs": [
            {
                "repair_id": r.repair_id,
                "repair_date": str(r.repair_date),
                "repair_cost": float(r.repair_cost),
                "repair_description": r.repair_description,
                "is_capitalized": r.is_capitalized,
            }
            for r in asset.repairs
        ],
    }


@router.post("/schedules/{schedule_id}/post", summary="Post Depreciation Period to General Ledger")
async def post_depreciation(schedule_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        gl_entry = await asset_service.post_depreciation_entry(db, tenant_id, schedule_id)
        return {
            "status": "POSTED",
            "schedule_id": schedule_id,
            "transaction_id": gl_entry.transaction_id,
            "posting_date": str(gl_entry.posting_date),
            "amount": float(gl_entry.debit_amount),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{asset_id}/move", summary="Record Asset Movement / Custodian Handover")
async def move_asset(asset_id: uuid.UUID, req: AssetMovementSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        m = await asset_service.record_asset_movement(
            session=db,
            tenant_id=tenant_id,
            asset_id=asset_id,
            to_location_id=req.to_location_id,
            to_custodian_id=req.to_custodian_id,
            movement_date=req.movement_date,
            purpose=req.purpose,
        )
        return {"movement_id": m.movement_id, "asset_id": asset_id, "movement_date": str(m.movement_date)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{asset_id}/repair", summary="Record Asset Repair & Optional Capitalization")
async def repair_asset(asset_id: uuid.UUID, req: AssetRepairSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        r = await asset_service.record_asset_repair(
            session=db,
            tenant_id=tenant_id,
            asset_id=asset_id,
            repair_cost=req.repair_cost,
            repair_description=req.repair_description,
            repair_date=req.repair_date,
            is_capitalized=req.is_capitalized,
        )
        return {
            "repair_id": r.repair_id,
            "repair_cost": float(r.repair_cost),
            "is_capitalized": r.is_capitalized,
            "journal_entry_id": r.journal_entry_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{asset_id}/scrap", summary="Scrap Asset & Write Off Remaining Book Value")
async def scrap_asset(asset_id: uuid.UUID, req: AssetScrapSchema, tenant_id: TenantIdDep, db: DbSessionDep):
    try:
        a = await asset_service.scrap_asset(
            session=db,
            tenant_id=tenant_id,
            asset_id=asset_id,
            disposal_date=req.disposal_date,
            notes=req.notes,
        )
        return {
            "asset_id": a.asset_id,
            "status": a.status,
            "current_book_value": float(a.current_book_value),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
