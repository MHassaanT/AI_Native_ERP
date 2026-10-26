"""Material Request (Requisition) and Automated Replenishment Service."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.hr import Employee
from erp.db.models.ledger import CostCenter
from erp.db.models.projects import Project
from erp.db.models.purchasing import (
    DocumentAuditBatch,
    MaterialRequest,
    MaterialRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from erp.db.models.shared_master import UOM, UOMConversion
from erp.db.models.shared_master import TermsAndConditionsTemplate


class RequisitionService:
    """Core domain logic for Material Requests and replenishment."""

    async def create_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_number: str,
        material_request_type: str = "PURCHASE",
        schedule_date: date | None = None,
        notes: str | None = None,
        requester_employee_id: uuid.UUID | None = None,
        external_reference: str | None = None,
        terms_template_id: uuid.UUID | None = None,
        terms_text: str | None = None,
        required_by_date: date | None = None,
        department: str | None = None,
        project_id: uuid.UUID | None = None,
        cost_center_id: uuid.UUID | None = None,
        attachments: list[dict[str, Any]] | None = None,
        source_warehouse_id: uuid.UUID | None = None,
        amended_from_mr_id: uuid.UUID | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> MaterialRequest:
        """Creates a new Material Request (Requisition)."""
        if not schedule_date:
            schedule_date = date.today() + timedelta(days=7)

        req = MaterialRequest(
            tenant_id=tenant_id,
            mr_number=mr_number,
            material_request_type=material_request_type.upper(),
            schedule_date=schedule_date,
            required_by_date=required_by_date or schedule_date,
            status="DRAFT",
            notes=notes,
            requester_employee_id=requester_employee_id,
            external_reference=external_reference,
            terms_template_id=terms_template_id,
            terms_text=terms_text,
            department=department,
            project_id=project_id,
            cost_center_id=cost_center_id,
            attachments=attachments,
            source_warehouse_id=source_warehouse_id,
            amended_from_mr_id=amended_from_mr_id,
        )
        session.add(req)
        await session.flush()

        if items:
            for it in items:
                item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
                quantity = Decimal(str(it["quantity"]))
                uom_id = uuid.UUID(str(it["uom_id"])) if it.get("uom_id") and isinstance(it["uom_id"], str) else it.get("uom_id")
                uom_label, factor = await self._uom_snapshot(session, tenant_id, item_id, uom_id, it.get("uom"))
                stock_quantity = (quantity * factor).quantize(Decimal("0.0001"))
                req_item = MaterialRequestItem(
                    tenant_id=tenant_id,
                    mr_id=req.mr_id,
                    item_id=item_id,
                    quantity=quantity,
                    ordered_qty=Decimal("0.0000"),
                    target_warehouse_id=(
                        uuid.UUID(str(it["target_warehouse_id"]))
                        if it.get("target_warehouse_id")
                        else None
                    ),
                    uom=uom_label,
                    uom_id=uom_id,
                    conversion_factor=factor,
                    stock_quantity=stock_quantity,
                )
                session.add(req_item)
            await session.flush()

        # Reload with items
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.mr_id == req.mr_id)
        )
        result = (await session.execute(stmt)).scalar_one()
        return result

    @staticmethod
    async def _uom_snapshot(session: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID,
                            uom_id: uuid.UUID | None, legacy_label: str | None) -> tuple[str, Decimal]:
        item = await session.scalar(select(Item).where(Item.tenant_id == tenant_id, Item.item_id == item_id))
        if item is None:
            raise ValueError("Material request item must belong to this workspace.")
        if uom_id is None:
            return legacy_label or item.stock_uom, Decimal("1")
        selected = await session.scalar(select(UOM).where(
            UOM.tenant_id == tenant_id, UOM.uom_id == uom_id, UOM.is_active.is_(True)))
        if selected is None:
            raise ValueError("UOM must be active and belong to this workspace.")
        stock_uom = await session.scalar(select(UOM).where(
            UOM.tenant_id == tenant_id, UOM.is_active.is_(True),
            or_(func.lower(UOM.abbreviation) == item.stock_uom.lower(),
                func.lower(UOM.uom_name) == item.stock_uom.lower())))
        if stock_uom is None:
            raise ValueError(f"Stock UOM '{item.stock_uom}' is not configured in this workspace.")
        if selected.uom_id == stock_uom.uom_id:
            return selected.abbreviation, Decimal("1")
        direct = await session.scalar(select(UOMConversion).where(
            UOMConversion.tenant_id == tenant_id, UOMConversion.from_uom_id == selected.uom_id,
            UOMConversion.to_uom_id == stock_uom.uom_id,
            or_(UOMConversion.item_id == item_id, UOMConversion.item_id.is_(None)))
            .order_by(UOMConversion.item_id.is_not(None).desc()))
        if direct is not None:
            return selected.abbreviation, Decimal(direct.factor)
        reverse = await session.scalar(select(UOMConversion).where(
            UOMConversion.tenant_id == tenant_id, UOMConversion.from_uom_id == stock_uom.uom_id,
            UOMConversion.to_uom_id == selected.uom_id,
            or_(UOMConversion.item_id == item_id, UOMConversion.item_id.is_(None)))
            .order_by(UOMConversion.item_id.is_not(None).desc()))
        if reverse is not None:
            return selected.abbreviation, Decimal("1") / Decimal(reverse.factor)
        raise ValueError(f"No conversion is configured from {selected.abbreviation} to stock UOM {item.stock_uom}.")

    async def update_draft_material_request(self, session: AsyncSession, tenant_id: uuid.UUID,
                                            mr_id: uuid.UUID, values: dict[str, Any]) -> MaterialRequest:
        req = (await session.execute(select(MaterialRequest)
            .options(selectinload(MaterialRequest.items))
            .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
            .with_for_update())).scalar_one_or_none()
        if req is None:
            raise ValueError("Material Request not found in this workspace.")
        if req.status != "DRAFT" or any(line.ordered_qty > 0 for line in req.items):
            raise ValueError("Only an unconverted draft request can be edited; create an amendment for submitted requests.")
        for model, pk, value, label, active_col in (
            (Project, Project.project_id, values.get("project_id"), "Project", Project.status),
            (CostCenter, CostCenter.cost_center_id, values.get("cost_center_id"), "Cost center", CostCenter.is_active),
            (Employee, Employee.employee_id, values.get("requester_employee_id"), "Requester", Employee.is_active),
            (TermsAndConditionsTemplate, TermsAndConditionsTemplate.terms_template_id, values.get("terms_template_id"), "Terms template", TermsAndConditionsTemplate.is_active),
        ):
            if value is not None:
                active_filter = active_col != "CANCELLED" if model is Project else active_col.is_(True)
                if await session.scalar(select(pk).where(model.tenant_id == tenant_id, pk == value, active_filter)) is None:
                    raise ValueError(f"{label} must be valid in this workspace.")
        if values.get("source_warehouse_id") and await session.scalar(select(Warehouse.warehouse_id).where(
            Warehouse.tenant_id == tenant_id, Warehouse.warehouse_id == values["source_warehouse_id"],
            Warehouse.is_active.is_(True))) is None:
            raise ValueError("Source warehouse must be active in this workspace.")
        line_values = values.get("items") or []
        target_ids = {line.get("target_warehouse_id") for line in line_values if line.get("target_warehouse_id")}
        if target_ids:
            found = set((await session.scalars(select(Warehouse.warehouse_id).where(
                Warehouse.tenant_id == tenant_id, Warehouse.warehouse_id.in_(target_ids), Warehouse.is_active.is_(True)))).all())
            if found != target_ids:
                raise ValueError("Every target warehouse must be active in this workspace.")
        req.mr_number = values["mr_number"]
        req.material_request_type = values["material_request_type"].upper()
        req.schedule_date = values["schedule_date"]
        req.required_by_date = values.get("required_by_date") or values["schedule_date"]
        req.notes = values.get("notes")
        req.requester_employee_id = values.get("requester_employee_id")
        req.external_reference = values.get("external_reference")
        req.terms_template_id = values.get("terms_template_id")
        req.terms_text = values.get("terms_text")
        req.department = values.get("department")
        req.project_id = values.get("project_id")
        req.cost_center_id = values.get("cost_center_id")
        req.source_warehouse_id = values.get("source_warehouse_id")
        req.attachments = values.get("attachments") or []
        req.items.clear()
        await session.flush()
        for line in line_values:
            item_id = uuid.UUID(str(line["item_id"])) if isinstance(line["item_id"], str) else line["item_id"]
            qty = Decimal(str(line["quantity"]))
            uom_id = uuid.UUID(str(line["uom_id"])) if line.get("uom_id") and isinstance(line["uom_id"], str) else line.get("uom_id")
            label, factor = await self._uom_snapshot(session, tenant_id, item_id, uom_id, line.get("uom"))
            req.items.append(MaterialRequestItem(tenant_id=tenant_id, item_id=item_id, quantity=qty,
                ordered_qty=Decimal("0"), target_warehouse_id=line.get("target_warehouse_id"),
                uom=label, uom_id=uom_id, conversion_factor=factor,
                stock_quantity=(qty * factor).quantize(Decimal("0.0001"))))
        await session.flush()
        return req

    async def amend_material_request(self, session: AsyncSession, tenant_id: uuid.UUID,
                                     mr_id: uuid.UUID, mr_number: str) -> MaterialRequest:
        original = (await session.execute(select(MaterialRequest)
            .options(selectinload(MaterialRequest.items))
            .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
            .with_for_update())).scalar_one_or_none()
        if original is None:
            raise ValueError("Material Request not found in this workspace.")
        if original.status not in {"SUBMITTED", "PARTIALLY_ORDERED", "ORDERED"}:
            raise ValueError("Only submitted requests can be amended; edit a draft directly.")
        remaining = [(line, Decimal(line.quantity) - Decimal(line.ordered_qty)) for line in original.items
                     if Decimal(line.quantity) > Decimal(line.ordered_qty)]
        if not remaining:
            raise ValueError("The request has no unconverted quantity to amend.")
        amendment_lines = [MaterialRequestItem(
                tenant_id=tenant_id, item_id=source_line.item_id, quantity=quantity, ordered_qty=Decimal("0"),
                target_warehouse_id=source_line.target_warehouse_id, uom=source_line.uom,
                uom_id=source_line.uom_id, conversion_factor=source_line.conversion_factor,
                stock_quantity=(quantity * Decimal(source_line.conversion_factor)).quantize(Decimal("0.0001")),
                source_mr_item_id=source_line.mr_item_id,
            ) for source_line, quantity in remaining]
        amendment = MaterialRequest(
            tenant_id=tenant_id, mr_number=mr_number, material_request_type=original.material_request_type,
            schedule_date=original.schedule_date, required_by_date=original.required_by_date,
            status="DRAFT", notes=original.notes, requester_employee_id=original.requester_employee_id,
            external_reference=original.external_reference, terms_template_id=original.terms_template_id,
            terms_text=original.terms_text, department=original.department, project_id=original.project_id,
            cost_center_id=original.cost_center_id, attachments=list(original.attachments or []),
            source_warehouse_id=original.source_warehouse_id, amended_from_mr_id=original.mr_id,
            items=amendment_lines,
        )
        session.add(amendment)
        await session.flush()
        return amendment

    async def submit_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest:
        """Transitions material request from DRAFT to SUBMITTED."""
        req = (
            await session.execute(
                select(MaterialRequest)
                .options(
                    selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                    selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
                )
                .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status != "DRAFT":
            raise ValueError(f"Cannot submit request with status '{req.status}'. Must be DRAFT.")
        req.status = "SUBMITTED"
        await session.flush()
        return req

    async def cancel_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest:
        """Cancels a material request."""
        req = (
            await session.execute(
                select(MaterialRequest)
                .options(
                    selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                    selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
                )
                .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status in ("ORDERED", "CANCELLED"):
            raise ValueError(f"Cannot cancel request in status '{req.status}'.")
        req.status = "CANCELLED"
        await session.flush()
        return req

    async def get_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
    ) -> MaterialRequest | None:
        """Fetches material request with related items."""
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.tenant_id == tenant_id, MaterialRequest.mr_id == mr_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_material_requests(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
        material_request_type: str | None = None,
    ) -> list[MaterialRequest]:
        """Lists material requests for a tenant."""
        stmt = (
            select(MaterialRequest)
            .options(
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.item),
                selectinload(MaterialRequest.items).selectinload(MaterialRequestItem.target_warehouse),
            )
            .where(MaterialRequest.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(MaterialRequest.status == status.upper())
        if material_request_type:
            stmt = stmt.where(MaterialRequest.material_request_type == material_request_type.upper())
        stmt = stmt.order_by(MaterialRequest.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def create_po_from_material_request(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        mr_id: uuid.UUID,
        supplier_id: uuid.UUID,
        po_number: str,
        items_to_order: list[dict[str, Any]] | None = None,
    ) -> PurchaseOrder:
        """Converts pending items in a submitted Material Request into a Purchase Order."""
        req = await self.get_material_request(session, tenant_id, mr_id)
        if not req:
            raise ValueError(f"Material Request {mr_id} not found.")
        if req.status not in ("SUBMITTED", "PARTIALLY_ORDERED"):
            raise ValueError(f"Material Request must be SUBMITTED or PARTIALLY_ORDERED, got {req.status}")

        req_items_by_id = {item.mr_item_id: item for item in req.items}
        # The header lock serializes conversions; lock child rows in stable order as
        # well so concurrent edits cannot oversubscribe individual request lines.
        locked_items = (
            await session.execute(
                select(MaterialRequestItem)
                .where(MaterialRequestItem.tenant_id == tenant_id, MaterialRequestItem.mr_id == mr_id)
                .order_by(MaterialRequestItem.mr_item_id)
                .with_for_update()
            )
        ).scalars().all()
        req_items_by_id = {item.mr_item_id: item for item in req.items}
        supplier = await session.scalar(
            select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.supplier_id == supplier_id,
                Supplier.is_active.is_(True),
            )
        )
        if supplier is None:
            raise ValueError("Supplier must be active and belong to this workspace.")
        po_lines: list[PurchaseOrderItem] = []
        total_subtotal = Decimal("0.0000")

        if not items_to_order:
            # Order all pending items
            items_to_order = []
            for item in req.items:
                remaining_qty = item.quantity - item.ordered_qty
                if remaining_qty > Decimal("0.0000"):
                    items_to_order.append({
                        "mr_item_id": item.mr_item_id,
                        "quantity": remaining_qty,
                    })

        if not items_to_order:
            raise ValueError("No eligible pending items to order in this Material Request.")

        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_number=po_number,
            supplier_id=supplier_id,
            material_request_id=req.mr_id,
            order_date=date.today(),
            currency=supplier.currency,
            subtotal=Decimal("0.0000"),
            tax_amount=Decimal("0.0000"),
            total_amount=Decimal("0.0000"),
            status="SUBMITTED",
            submitted_at=datetime.now(UTC),
            terms_template_id=req.terms_template_id,
            terms_text=req.terms_text,
            required_by_date=req.required_by_date,
            department=req.department,
            project_id=req.project_id,
            cost_center_id=req.cost_center_id,
            attachments=req.attachments or [],
            source_warehouse_id=req.source_warehouse_id,
            payment_terms=f"Net {supplier.payment_terms_days} days",
        )
        session.add(po)
        await session.flush()
        session.add(DocumentAuditBatch(
            tenant_id=tenant_id,
            operation="PURCHASE_ORDER_SUBMITTED",
            idempotency_key=str(po.po_id),
            status="COMPLETED",
            input_snapshot={"po_number": po.po_number, "material_request_id": str(req.mr_id)},
            result_snapshot={"po_id": str(po.po_id), "status": po.status},
            completed_at=datetime.now(UTC),
        ))

        for ord_info in items_to_order:
            mr_item_id = (
                uuid.UUID(str(ord_info["mr_item_id"]))
                if isinstance(ord_info["mr_item_id"], str)
                else ord_info["mr_item_id"]
            )
            mr_item = req_items_by_id.get(mr_item_id)
            if not mr_item:
                raise ValueError(f"Line item {mr_item_id} not found in Material Request {mr_id}.")

            qty = Decimal(str(ord_info["quantity"]))
            remaining_qty = mr_item.quantity - mr_item.ordered_qty
            if qty > remaining_qty:
                raise ValueError(
                    f"Requested quantity {qty} exceeds pending quantity {remaining_qty} for item {mr_item.item.item_code}."
                )

            # Get price from item standard_rate or input
            unit_price = Decimal(str(ord_info.get("unit_price", mr_item.item.standard_rate or "0.0000")))
            line_total = qty * unit_price
            total_subtotal += line_total

            po_item = PurchaseOrderItem(
                tenant_id=tenant_id,
                po_id=po.po_id,
                item_id=mr_item.item_id,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                material_request_item_id=mr_item.mr_item_id,
                uom_id=mr_item.uom_id,
                conversion_factor=mr_item.conversion_factor,
                stock_quantity=(qty * mr_item.conversion_factor).quantize(Decimal("0.0001")),
                target_warehouse_id=mr_item.target_warehouse_id,
            )
            session.add(po_item)
            mr_item.ordered_qty += qty

        po.subtotal = total_subtotal
        po.total_amount = total_subtotal

        # Check overall MR status
        all_ordered = all(it.ordered_qty >= it.quantity for it in req.items)
        req.status = "ORDERED" if all_ordered else "PARTIALLY_ORDERED"

        await session.flush()
        return po

    async def check_reorder_replenishment(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[MaterialRequest]:
        """Scans inventory levels vs reorder levels and creates Material Requests for depleted items."""
        # Find all purchase items with reorder_level > 0
        items_stmt = select(Item).where(
            Item.tenant_id == tenant_id,
            Item.is_purchase_item == True,
            Item.is_stock_item == True,
            Item.is_active == True,
            Item.reorder_level > Decimal("0.0000"),
        )
        items = (await session.execute(items_stmt)).scalars().all()

        created_mrs: list[MaterialRequest] = []
        depleted_lines: list[dict[str, Any]] = []

        for item in items:
            # Calculate total stock on hand across all warehouses
            stock_stmt = select(func.coalesce(func.sum(StockLevel.current_qty), 0)).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == item.item_id,
            )
            current_qty = Decimal(str((await session.execute(stock_stmt)).scalar() or 0))

            # If current stock is below or equal to reorder level
            if current_qty <= item.reorder_level:
                # Reorder quantity: target at least 2x reorder level or deficit
                deficit = (item.reorder_level * 2) - current_qty
                if deficit <= Decimal("0.0000"):
                    deficit = item.reorder_level

                depleted_lines.append({
                    "item_id": item.item_id,
                    "quantity": deficit,
                    "uom": item.stock_uom,
                })

        if depleted_lines:
            mr_number = f"MR-AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            mr = await self.create_material_request(
                session=session,
                tenant_id=tenant_id,
                mr_number=mr_number,
                material_request_type="PURCHASE",
                schedule_date=date.today() + timedelta(days=7),
                notes="Automated replenishment material request triggered by safety stock thresholds.",
                items=depleted_lines,
            )
            created_mrs.append(mr)

        return created_mrs


requisition_service = RequisitionService()
