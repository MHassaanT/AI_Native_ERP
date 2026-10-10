"""Inventory Replenishment and Dynamic ROP API Endpoints."""

import csv
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated
from zipfile import BadZipFile

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.inventory import Item, ItemTodo, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.purchasing import PurchaseOrder, PurchaseOrderItem, Supplier
from erp.db.models.sales import (
    Customer,
    SalesInvoice,
    SalesInvoiceItem,
)
from erp.supply_chain.replenishment import (
    ReplenishmentEvaluationResult,
    replenishment_coordinator,
)
from erp.supply_chain.rop_engine import ROPEvaluation, rop_engine

router = APIRouter(prefix="/inventory", tags=["Dynamic Inventory & Replenishment"])


class CreateItemRequest(BaseModel):
    item_code: str = Field(..., min_length=2, max_length=64)
    item_name: str = Field(..., min_length=2, max_length=255)
    stock_uom: str = "Nos"
    standard_rate: Decimal = Field(default=Decimal("0.0000"), ge=0)
    reorder_level: Decimal = Field(default=Decimal("100.0000"), ge=0)
    initial_qty: Decimal = Field(default=Decimal("0.0000"), ge=0)
    description: str | None = None
    barcode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    package_quantity: str | None = Field(default=None, max_length=128)
    image_url: str | None = None
    is_stock_item: bool = True
    is_sales_item: bool = True
    is_purchase_item: bool = True


class UpdateItemRequest(BaseModel):
    item_name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    barcode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    package_quantity: str | None = Field(default=None, max_length=128)
    image_url: str | None = None
    stock_uom: str | None = Field(default=None, max_length=32)
    standard_rate: Decimal | None = Field(default=None, ge=0)
    reorder_level: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CreateItemTodoRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    due_date: date | None = None


class UpdateItemTodoRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(TODO|IN_PROGRESS|DONE)$")
    assigned_to: str | None = Field(default=None, max_length=255)
    due_date: date | None = None


class StockAdjustmentRequest(BaseModel):
    item_id: uuid.UUID
    delta_qty: Decimal
    reason: str = "MANUAL_ADJUSTMENT"


class CalculateROPRequest(BaseModel):
    item_code: str
    daily_demand_mean: Decimal = Decimal("150.0000")
    daily_demand_std: Decimal = Decimal("25.0000")
    lead_time_mean_days: Decimal = Decimal("14.0000")
    lead_time_std_days: Decimal = Decimal("3.0000")


async def _default_warehouse(tenant_id: uuid.UUID, db: DbSessionDep) -> Warehouse:
    warehouse = (
        await db.execute(select(Warehouse).where(Warehouse.tenant_id == tenant_id))
    ).scalars().first()
    if not warehouse:
        warehouse = Warehouse(
            tenant_id=tenant_id,
            warehouse_code="WH-MAIN-01",
            warehouse_name="Central Industrial Warehouse",
        )
        db.add(warehouse)
        await db.flush()
    return warehouse


def _build_inventory_records(
    req: CreateItemRequest,
    tenant_id: uuid.UUID,
    warehouse: Warehouse,
) -> tuple[Item, StockLevel, StockLedgerEntry | None]:
    item_id = uuid.uuid4()
    item = Item(
        item_id=item_id,
        tenant_id=tenant_id,
        item_code=req.item_code,
        item_name=req.item_name,
        description=req.description,
        barcode=req.barcode,
        brand=req.brand,
        category=req.category,
        package_quantity=req.package_quantity,
        image_url=req.image_url,
        stock_uom=req.stock_uom,
        standard_rate=req.standard_rate,
        reorder_level=req.reorder_level,
        is_stock_item=req.is_stock_item,
        is_sales_item=req.is_sales_item,
        is_purchase_item=req.is_purchase_item,
        is_active=True,
    )
    stock = StockLevel(
        tenant_id=tenant_id,
        item_id=item_id,
        warehouse_id=warehouse.warehouse_id,
        current_qty=req.initial_qty,
        reserved_qty=Decimal("0.0000"),
        available_qty=req.initial_qty,
        valuation_rate=req.standard_rate,
    )
    ledger_entry = (
        StockLedgerEntry(
            tenant_id=tenant_id,
            posting_datetime=datetime.now(UTC),
            item_id=item_id,
            warehouse_id=warehouse.warehouse_id,
            actual_qty=req.initial_qty,
            qty_after_transaction=req.initial_qty,
            incoming_rate=req.standard_rate,
            valuation_rate=req.standard_rate,
            source_document_type="OPENING_STOCK",
            source_document_id=uuid.uuid4(),
        )
        if req.initial_qty > 0
        else None
    )
    return item, stock, ledger_entry


async def _create_item(
    req: CreateItemRequest,
    tenant_id: uuid.UUID,
    warehouse: Warehouse,
    db: DbSessionDep,
) -> Item:
    item, stock, ledger_entry = _build_inventory_records(req, tenant_id, warehouse)
    db.add_all([item, stock] + ([ledger_entry] if ledger_entry else []))
    await db.flush()
    return item


@router.get("/items", summary="List inventory items with stock levels")
async def list_inventory_items(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns items with on-hand and available quantities for the tenant."""
    stmt = (
        select(
            Item,
            func.coalesce(func.sum(StockLevel.current_qty), 0),
            func.coalesce(func.sum(StockLevel.reserved_qty), 0),
            func.coalesce(func.sum(StockLevel.available_qty), 0),
            func.coalesce(func.max(StockLevel.valuation_rate), Item.standard_rate),
        )
        .outerjoin(
            StockLevel,
            (StockLevel.item_id == Item.item_id) & (StockLevel.tenant_id == Item.tenant_id),
        )
        .where(Item.tenant_id == tenant_id)
        .group_by(Item.item_id)
        .order_by(Item.item_code.asc())
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for item, curr_qty, res_qty, avail_qty, val_rate in rows:
        items.append(
            {
                "item_id": str(item.item_id),
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "barcode": item.barcode,
                "brand": item.brand,
                "category": item.category,
                "package_quantity": item.package_quantity,
                "image_url": item.image_url,
                "stock_uom": item.stock_uom,
                "standard_rate": str(item.standard_rate),
                "reorder_level": str(item.reorder_level),
                "current_qty": str(curr_qty if curr_qty is not None else Decimal("0.0000")),
                "reserved_qty": str(res_qty if res_qty is not None else Decimal("0.0000")),
                "available_qty": str(avail_qty if avail_qty is not None else Decimal("0.0000")),
                "valuation_rate": str(val_rate if val_rate is not None else item.standard_rate),
                "is_active": item.is_active,
            }
        )
    return items


@router.post("/items", status_code=status.HTTP_201_CREATED, summary="Create inventory item")
async def create_inventory_item(req: CreateItemRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Registers a new item in the master catalog and creates initial stock entry."""
    existing = (
        await db.execute(
            select(Item).where(Item.tenant_id == tenant_id, Item.item_code == req.item_code)
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item with code '{req.item_code}' already exists.",
        )

    warehouse = await _default_warehouse(tenant_id, db)
    return await _create_item(req, tenant_id, warehouse, db)


@router.post("/items/import", summary="Import inventory items from CSV or XLSX")
async def import_inventory_items(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    file: Annotated[UploadFile, File(...)],
):
    """Import up to 5,000 catalog rows, reporting invalid rows while saving valid ones."""
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Upload a .csv or .xlsx file.")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Import files must be 10 MB or smaller.")

    try:
        rows = []
        if filename.endswith(".csv"):
            source_rows = csv.reader(io.StringIO(content.decode("utf-8-sig")))
        else:
            from openpyxl import load_workbook

            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            worksheet = workbook.active
            source_rows = worksheet.iter_rows(values_only=True)
        for row in source_rows:
            if len(rows) >= 5001:
                if not filename.endswith(".csv"):
                    workbook.close()
                raise HTTPException(
                    status_code=400, detail="Import files may contain at most 5,000 items."
                )
            rows.append(row)
        if not filename.endswith(".csv"):
            workbook.close()
    except (UnicodeDecodeError, csv.Error, ValueError, OSError, BadZipFile) as exc:
        raise HTTPException(status_code=400, detail=f"Could not read import file: {exc}") from exc

    if not rows or len(rows) < 2:
        raise HTTPException(status_code=400, detail="The import file must include a header and rows.")
    def normalized(value: object) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    def as_decimal(values: dict[str, object], key: str, default: str) -> Decimal:
        value = values[key]
        return (
            Decimal(str(value).strip())
            if value is not None and str(value).strip()
            else Decimal(default)
        )

    headers = [normalized(value) for value in rows[0]]
    aliases = {
        "item_code": {"item_code", "sku", "code", "internal_reference"},
        "item_name": {"item_name", "product_name", "name", "product"},
        "description": {"description", "details"},
        "barcode": {"barcode", "gtin", "ean", "upc"},
        "brand": {"brand", "manufacturer"},
        "category": {"category", "product_category"},
        "package_quantity": {"package_quantity", "package_size", "pack_size"},
        "image_url": {"image_url", "image", "image_link"},
        "stock_uom": {"stock_uom", "uom", "unit"},
        "standard_rate": {"standard_rate", "price", "unit_price", "cost"},
        "initial_qty": {"initial_qty", "quantity", "initial_stock", "qty"},
        "reorder_level": {"reorder_level", "reorder_point", "safety_stock"},
    }
    column_index = {
        field: next((index for index, header in enumerate(headers) if header in names), None)
        for field, names in aliases.items()
    }
    missing = [field for field in ("item_code", "item_name") if column_index[field] is None]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"Missing required columns: {', '.join(missing)}."
        )

    existing_codes = set(
        (await db.execute(select(Item.item_code).where(Item.tenant_id == tenant_id))).scalars()
    )
    errors: list[dict[str, object]] = []
    created = 0
    warehouse: Warehouse | None = None

    for row_number, row in enumerate(rows[1:], start=2):
        values = {
            key: row[index] if index is not None and index < len(row) else None
            for key, index in column_index.items()
        }
        if not any(value is not None and str(value).strip() for value in values.values()):
            continue
        code = str(values["item_code"] or "").strip()
        name = str(values["item_name"] or "").strip()
        if not code or not name:
            errors.append({"row": row_number, "error": "Item code and item name are required."})
            continue
        if code in existing_codes:
            errors.append({"row": row_number, "error": f"Item code '{code}' already exists."})
            continue

        try:
            req = CreateItemRequest(
                item_code=code,
                item_name=name,
                description=str(values["description"]).strip() if values["description"] else None,
                barcode=str(values["barcode"]).strip() if values["barcode"] else None,
                brand=str(values["brand"]).strip() if values["brand"] else None,
                category=str(values["category"]).strip() if values["category"] else None,
                package_quantity=(
                    str(values["package_quantity"]).strip() if values["package_quantity"] else None
                ),
                image_url=str(values["image_url"]).strip() if values["image_url"] else None,
                stock_uom=str(values["stock_uom"] or "Nos").strip(),
                standard_rate=as_decimal(values, "standard_rate", "0"),
                initial_qty=as_decimal(values, "initial_qty", "0"),
                reorder_level=as_decimal(values, "reorder_level", "0"),
            )
            if req.initial_qty < 0 or req.standard_rate < 0 or req.reorder_level < 0:
                raise ValueError("Quantity, rate, and reorder level cannot be negative.")
        except (InvalidOperation, ValueError, ValidationError) as exc:
            errors.append({"row": row_number, "error": f"Invalid item data: {exc}"})
            continue
        if not all(
            amount.is_finite()
            for amount in (req.initial_qty, req.standard_rate, req.reorder_level)
        ):
            errors.append({"row": row_number, "error": "Quantity, rate, and reorder level must be finite numbers."})
            continue

        warehouse = warehouse or await _default_warehouse(tenant_id, db)
        item, stock, ledger_entry = _build_inventory_records(req, tenant_id, warehouse)
        db.add_all([item, stock] + ([ledger_entry] if ledger_entry else []))
        existing_codes.add(code)
        created += 1

    if created:
        await db.flush()
    return {"created": created, "errors": errors, "total_rows": len(rows) - 1}


@router.get("/barcode/{barcode}", summary="Look up product details by barcode")
async def lookup_barcode(barcode: str):
    """Look up a scanned barcode in Open Food Facts; the user must verify the returned data."""
    code = barcode.strip()
    if not code.isdigit() or not 8 <= len(code) <= 14:
        raise HTTPException(status_code=422, detail="Enter a valid 8-14 digit product barcode.")
    url = f"https://world.openfoodfacts.org/api/v3/product/{code}"
    fields = "code,product_name,brands,categories,quantity,image_front_url,ingredients_text"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(6.0, connect=2.0),
            headers={"User-Agent": "AI-Native-ERP/1.0 (inventory product lookup)"},
        ) as client:
            response = await client.get(url, params={"fields": fields})
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Product barcode lookup timed out.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="No product found for this barcode.") from exc
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=503,
                detail="Open Food Facts rate limit reached (15 product lookups per minute per IP). Wait before retrying.",
            ) from exc
        raise HTTPException(status_code=502, detail="Product lookup provider returned an error.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the product lookup provider.") from exc

    try:
        payload = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Product lookup provider returned invalid data.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Product lookup provider returned invalid data.")
    product = payload.get("product")
    if not isinstance(product, dict):
        raise HTTPException(status_code=404, detail="No product found for this barcode.")
    return {
        "source": "Open Food Facts",
        "barcode": product.get("code") or code,
        "item_name": product.get("product_name") or "",
        "brand": product.get("brands") or "",
        "category": product.get("categories") or "",
        "package_quantity": product.get("quantity") or "",
        "description": product.get("ingredients_text") or "",
        "image_url": product.get("image_front_url") or "",
    }


@router.get("/items/{item_id}/overview", summary="Get item activity and sales overview")
async def get_item_overview(
    item_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    days: int = Query(default=30, ge=7, le=365),
):
    item = (
        await db.execute(select(Item).where(Item.item_id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    cutoff = date.today() - timedelta(days=days - 1)
    sales_rows = (
        await db.execute(
            select(
                SalesInvoice.invoice_id,
                SalesInvoice.invoice_date,
                SalesInvoiceItem.quantity,
                SalesInvoiceItem.line_total,
            )
            .join(SalesInvoice, SalesInvoice.invoice_id == SalesInvoiceItem.invoice_id)
            .where(
                SalesInvoiceItem.tenant_id == tenant_id,
                SalesInvoiceItem.item_id == item_id,
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.invoice_date >= cutoff,
                SalesInvoice.status != "CANCELLED",
            )
        )
    ).all()
    sales_by_day: dict[str, dict[str, Decimal]] = {}
    for _, invoice_date, quantity, line_total in sales_rows:
        key = invoice_date.isoformat()
        totals = sales_by_day.setdefault(key, {"quantity": Decimal("0"), "revenue": Decimal("0")})
        totals["quantity"] += quantity
        totals["revenue"] += line_total

    recent_invoices = (
        await db.execute(
            select(
                SalesInvoice.invoice_number,
                SalesInvoice.invoice_date,
                SalesInvoice.status,
                SalesInvoiceItem.quantity,
                SalesInvoiceItem.line_total,
                Customer.customer_name,
            )
            .join(SalesInvoice, SalesInvoice.invoice_id == SalesInvoiceItem.invoice_id)
            .join(Customer, Customer.customer_id == SalesInvoice.customer_id)
            .where(
                SalesInvoiceItem.tenant_id == tenant_id,
                SalesInvoiceItem.item_id == item_id,
                SalesInvoice.tenant_id == tenant_id,
                SalesInvoice.status != "CANCELLED",
            )
            .order_by(SalesInvoice.invoice_date.desc())
            .limit(10)
        )
    ).all()
    activity = (
        await db.execute(
            select(
                StockLedgerEntry.posting_datetime,
                StockLedgerEntry.actual_qty,
                StockLedgerEntry.source_document_type,
                StockLedgerEntry.source_document_id,
            )
            .where(
                StockLedgerEntry.tenant_id == tenant_id,
                StockLedgerEntry.item_id == item_id,
                StockLedgerEntry.is_cancelled.is_(False),
            )
            .order_by(StockLedgerEntry.posting_datetime.desc())
            .limit(30)
        )
    ).all()
    last_purchase = (
        await db.execute(
            select(
                PurchaseOrder.po_number,
                PurchaseOrder.order_date,
                PurchaseOrder.status,
                PurchaseOrderItem.quantity,
                PurchaseOrderItem.unit_price,
                Supplier.supplier_name,
            )
            .join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id)
            .join(Supplier, Supplier.supplier_id == PurchaseOrder.supplier_id)
            .where(
                PurchaseOrderItem.tenant_id == tenant_id,
                PurchaseOrderItem.item_id == item_id,
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.status.not_in(("CANCELLED", "DRAFT")),
            )
            .order_by(PurchaseOrder.order_date.desc())
            .limit(1)
        )
    ).first()
    sales_total = sum((row[3] for row in sales_rows), Decimal("0"))
    quantity_total = sum((row[2] for row in sales_rows), Decimal("0"))
    chart_data = []
    for offset in range(days):
        chart_date = cutoff + timedelta(days=offset)
        totals = sales_by_day.get(
            chart_date.isoformat(), {"quantity": Decimal("0"), "revenue": Decimal("0")}
        )
        chart_data.append(
            {
                "date": chart_date.isoformat(),
                "revenue": str(totals["revenue"]),
                "quantity": str(totals["quantity"]),
            }
        )
    return {
        "item_id": str(item.item_id),
        "sales": {
            "days": days,
            "revenue": str(sales_total),
            "quantity": str(quantity_total),
            "invoices": len({row[0] for row in sales_rows}),
            "by_day": chart_data,
            "recent_invoices": [
                {
                    "invoice_number": row[0],
                    "date": row[1].isoformat(),
                    "status": row[2],
                    "quantity": str(row[3]),
                    "revenue": str(row[4]),
                    "customer": row[5],
                }
                for row in recent_invoices
            ],
        },
        "activity": [
            {
                "date": row[0].isoformat(),
                "quantity": str(row[1]),
                "source": row[2],
                "document_id": str(row[3]),
            }
            for row in activity
        ],
        "last_purchase": (
            {
                "order_number": last_purchase[0],
                "date": last_purchase[1].isoformat(),
                "status": last_purchase[2],
                "quantity": str(last_purchase[3]),
                "unit_price": str(last_purchase[4]),
                "supplier": last_purchase[5],
            }
            if last_purchase
            else None
        ),
    }


@router.patch("/items/{item_id}", summary="Update inventory item settings")
async def update_inventory_item(
    item_id: uuid.UUID,
    req: UpdateItemRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    item = (
        await db.execute(select(Item).where(Item.item_id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    return {"item_id": str(item.item_id), "status": "updated"}


@router.get("/items/{item_id}/todos", summary="List item follow-up tasks")
async def list_item_todos(item_id: uuid.UUID, tenant_id: TenantIdDep, db: DbSessionDep):
    item = (
        await db.execute(select(Item.item_id).where(Item.item_id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    todos = (
        await db.execute(
            select(ItemTodo)
            .where(ItemTodo.item_id == item_id, ItemTodo.tenant_id == tenant_id)
            .order_by(ItemTodo.created_at.desc())
        )
    ).scalars()
    return [
        {
            "todo_id": str(todo.todo_id),
            "title": todo.title,
            "status": todo.status,
            "assigned_to": todo.assigned_to,
            "due_date": todo.due_date.isoformat() if todo.due_date else None,
        }
        for todo in todos
    ]


@router.post("/items/{item_id}/todos", status_code=status.HTTP_201_CREATED, summary="Add item task")
async def create_item_todo(
    item_id: uuid.UUID,
    req: CreateItemTodoRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    item = (
        await db.execute(select(Item.item_id).where(Item.item_id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    todo = ItemTodo(
        tenant_id=tenant_id,
        item_id=item_id,
        title=req.title,
        assigned_to=req.assigned_to,
        due_date=req.due_date,
    )
    db.add(todo)
    await db.flush()
    return {"todo_id": str(todo.todo_id), "title": todo.title, "status": todo.status}


@router.patch("/items/{item_id}/todos/{todo_id}", summary="Update item task")
async def update_item_todo(
    item_id: uuid.UUID,
    todo_id: uuid.UUID,
    req: UpdateItemTodoRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    todo = (
        await db.execute(
            select(ItemTodo).where(
                ItemTodo.todo_id == todo_id,
                ItemTodo.item_id == item_id,
                ItemTodo.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Item task not found.")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(todo, field, value)
    await db.flush()
    return {"todo_id": str(todo.todo_id), "status": todo.status}


@router.post("/stock-adjustment", summary="Adjust inventory stock level")
async def adjust_stock(req: StockAdjustmentRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Adjusts on-hand stock and appends immutable StockLedgerEntry."""
    stock = (
        await db.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == req.item_id,
            )
        )
    ).scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock level not found.")

    new_qty = stock.current_qty + req.delta_qty
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient inventory. Adjustment would result in negative stock ({new_qty}).",
        )

    stock.current_qty = new_qty
    stock.available_qty = new_qty - stock.reserved_qty

    sle = StockLedgerEntry(
        tenant_id=tenant_id,
        posting_datetime=datetime.now(UTC),
        item_id=req.item_id,
        warehouse_id=stock.warehouse_id,
        actual_qty=req.delta_qty,
        qty_after_transaction=new_qty,
        valuation_rate=stock.valuation_rate,
        source_document_type=req.reason,
        source_document_id=uuid.uuid4(),
    )
    db.add(sle)
    await db.flush()
    return {
        "status": "SUCCESS",
        "current_qty": str(new_qty),
        "available_qty": str(stock.available_qty),
    }


@router.post(
    "/calculate-rop",
    response_model=ROPEvaluation,
    summary="Calculate dynamic Reorder Point (ROP)",
)
async def calculate_dynamic_rop_endpoint(req: CalculateROPRequest):
    """Calculates stochastic ROP incorporating demand and lead-time distributions (Z=2.33)."""
    return rop_engine.calculate_rop(
        item_code=req.item_code,
        mu_d=req.daily_demand_mean,
        sigma_d=req.daily_demand_std,
        mu_l=req.lead_time_mean_days,
        sigma_l=req.lead_time_std_days,
    )


@router.post(
    "/replenish/{item_id}",
    response_model=ReplenishmentEvaluationResult,
    summary="Evaluate stock and trigger automated replenishment",
)
async def evaluate_and_replenish_endpoint(
    item_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Evaluates OnHand + OnOrder <= ROP. Autonomously generates Purchase Order if triggered."""
    try:
        return await replenishment_coordinator.evaluate_and_replenish_item(
            session=db,
            tenant_id=tenant_id,
            item_id=item_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
