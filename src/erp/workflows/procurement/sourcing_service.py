"""Strategic Sourcing, RFQs, Supplier Quotations, and Matrix Comparison Service."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item
from erp.db.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    RequestForQuotation,
    RFQItem,
    RFQSupplier,
    Supplier,
    SupplierQuotation,
    SupplierQuotationItem,
)


class SourcingService:
    """Core domain logic for RFQs, quotation comparison matrices, and awarding."""

    async def create_rfq(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rfq_number: str,
        transaction_date: date | None = None,
        notes: str | None = None,
        supplier_ids: list[uuid.UUID] | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> RequestForQuotation:
        """Creates a Request For Quotation."""
        if not transaction_date:
            transaction_date = date.today()

        rfq = RequestForQuotation(
            tenant_id=tenant_id,
            rfq_number=rfq_number,
            transaction_date=transaction_date,
            status="DRAFT",
            notes=notes,
        )
        session.add(rfq)
        await session.flush()

        if supplier_ids:
            for s_id in supplier_ids:
                supp_id = uuid.UUID(str(s_id)) if isinstance(s_id, str) else s_id
                rfq_sup = RFQSupplier(
                    tenant_id=tenant_id,
                    rfq_id=rfq.rfq_id,
                    supplier_id=supp_id,
                    email_sent=False,
                    quote_status="PENDING",
                )
                session.add(rfq_sup)

        if items:
            for it in items:
                req_date = it.get("required_date")
                if isinstance(req_date, str):
                    req_date = date.fromisoformat(req_date)
                rfq_it = RFQItem(
                    tenant_id=tenant_id,
                    rfq_id=rfq.rfq_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    quantity=Decimal(str(it["quantity"])),
                    required_date=req_date,
                )
                session.add(rfq_it)

        await session.flush()
        return await self.get_rfq(session, tenant_id, rfq.rfq_id)  # type: ignore

    async def send_rfq(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rfq_id: uuid.UUID,
    ) -> RequestForQuotation:
        """Marks RFQ as SENT and flags emails as sent to vendors."""
        rfq = await self.get_rfq(session, tenant_id, rfq_id)
        if not rfq:
            raise ValueError(f"RFQ {rfq_id} not found.")
        rfq.status = "SENT"
        for sup in rfq.suppliers:
            sup.email_sent = True
        await session.flush()
        return rfq

    async def get_rfq(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rfq_id: uuid.UUID,
    ) -> RequestForQuotation | None:
        """Fetches RFQ with items and suppliers."""
        stmt = (
            select(RequestForQuotation)
            .options(
                selectinload(RequestForQuotation.items).selectinload(RFQItem.item),
                selectinload(RequestForQuotation.suppliers).selectinload(RFQSupplier.supplier),
            )
            .where(RequestForQuotation.tenant_id == tenant_id, RequestForQuotation.rfq_id == rfq_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_rfqs(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[RequestForQuotation]:
        """Lists RFQs for the tenant."""
        stmt = (
            select(RequestForQuotation)
            .options(
                selectinload(RequestForQuotation.items).selectinload(RFQItem.item),
                selectinload(RequestForQuotation.suppliers).selectinload(RFQSupplier.supplier),
            )
            .where(RequestForQuotation.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(RequestForQuotation.status == status.upper())
        stmt = stmt.order_by(RequestForQuotation.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def create_supplier_quotation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        quotation_number: str,
        supplier_id: uuid.UUID,
        rfq_id: uuid.UUID | None = None,
        quotation_date: date | None = None,
        valid_until: date | None = None,
        currency: str = "USD",
        lead_time_days: int = 7,
        payment_terms: str | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> SupplierQuotation:
        """Submits or registers a vendor supplier quotation."""
        if not quotation_date:
            quotation_date = date.today()
        if not valid_until:
            valid_until = quotation_date + timedelta(days=30)

        subtotal = Decimal("0.0000")
        tax_amount = Decimal("0.0000")

        sq = SupplierQuotation(
            tenant_id=tenant_id,
            quotation_number=quotation_number,
            supplier_id=supplier_id,
            rfq_id=rfq_id,
            quotation_date=quotation_date,
            valid_until=valid_until,
            currency=currency,
            lead_time_days=lead_time_days,
            payment_terms=payment_terms,
            status="SUBMITTED",
            subtotal=Decimal("0.0000"),
            tax_amount=Decimal("0.0000"),
            grand_total=Decimal("0.0000"),
        )
        session.add(sq)
        await session.flush()

        if items:
            for it in items:
                qty = Decimal(str(it["quantity"]))
                rate = Decimal(str(it["unit_price"]))
                discount = Decimal(str(it.get("discount_pct", "0.00")))
                discounted_rate = rate * (Decimal("1.00") - (discount / Decimal("100.00")))
                line_total = qty * discounted_rate
                subtotal += line_total

                sq_item = SupplierQuotationItem(
                    tenant_id=tenant_id,
                    sq_id=sq.sq_id,
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    quantity=qty,
                    unit_price=rate,
                    discount_pct=discount,
                    line_total=line_total,
                    lead_time_days=int(it.get("lead_time_days", lead_time_days)),
                )
                session.add(sq_item)

        sq.subtotal = subtotal
        sq.grand_total = subtotal + tax_amount

        # Update RFQ supplier status if tied to an RFQ
        if rfq_id:
            rfq_sup_stmt = select(RFQSupplier).where(
                RFQSupplier.tenant_id == tenant_id,
                RFQSupplier.rfq_id == rfq_id,
                RFQSupplier.supplier_id == supplier_id,
            )
            rfq_sup = (await session.execute(rfq_sup_stmt)).scalar_one_or_none()
            if rfq_sup:
                rfq_sup.quote_status = "SUBMITTED"

            # Check if RFQ has quotes received
            rfq = await self.get_rfq(session, tenant_id, rfq_id)
            if rfq and rfq.status == "SENT":
                rfq.status = "QUOTES_RECEIVED"

        await session.flush()
        return await self.get_supplier_quotation(session, tenant_id, sq.sq_id)  # type: ignore

    async def get_supplier_quotation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sq_id: uuid.UUID,
    ) -> SupplierQuotation | None:
        """Fetches quotation with items and supplier info."""
        stmt = (
            select(SupplierQuotation)
            .options(
                selectinload(SupplierQuotation.items).selectinload(SupplierQuotationItem.item),
                selectinload(SupplierQuotation.supplier),
                selectinload(SupplierQuotation.rfq),
            )
            .where(SupplierQuotation.tenant_id == tenant_id, SupplierQuotation.sq_id == sq_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_supplier_quotations(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rfq_id: uuid.UUID | None = None,
        supplier_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[SupplierQuotation]:
        """Lists supplier quotations."""
        stmt = (
            select(SupplierQuotation)
            .options(
                selectinload(SupplierQuotation.items).selectinload(SupplierQuotationItem.item),
                selectinload(SupplierQuotation.supplier),
                selectinload(SupplierQuotation.rfq),
            )
            .where(SupplierQuotation.tenant_id == tenant_id)
        )
        if rfq_id:
            stmt = stmt.where(SupplierQuotation.rfq_id == rfq_id)
        if supplier_id:
            stmt = stmt.where(SupplierQuotation.supplier_id == supplier_id)
        if status:
            stmt = stmt.where(SupplierQuotation.status == status.upper())
        stmt = stmt.order_by(SupplierQuotation.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_quote_comparison_matrix(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        rfq_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Generates side-by-side comparison matrix for all bids received on an RFQ."""
        rfq = await self.get_rfq(session, tenant_id, rfq_id)
        if not rfq:
            raise ValueError(f"RFQ {rfq_id} not found.")

        # Load all quotes submitted for this RFQ
        quotes = await self.list_supplier_quotations(session, tenant_id, rfq_id=rfq_id)

        items_matrix = []
        overall_quotations = []

        for quote in quotes:
            overall_quotations.append({
                "sq_id": str(quote.sq_id),
                "quotation_number": quote.quotation_number,
                "supplier_id": str(quote.supplier_id),
                "supplier_name": quote.supplier.supplier_name if quote.supplier else "Unknown",
                "supplier_code": quote.supplier.supplier_code if quote.supplier else "Unknown",
                "otif_score": float(quote.supplier.otif_score) if quote.supplier else 100.0,
                "grand_total": float(quote.grand_total),
                "lead_time_days": quote.lead_time_days,
                "payment_terms": quote.payment_terms,
                "status": quote.status,
            })

        for rfq_item in rfq.items:
            item_id = rfq_item.item_id
            bids = []

            for quote in quotes:
                # Find matching quote item
                matching_items = [it for it in quote.items if it.item_id == item_id]
                for m in matching_items:
                    bids.append({
                        "sq_id": str(quote.sq_id),
                        "quotation_number": quote.quotation_number,
                        "supplier_id": str(quote.supplier_id),
                        "supplier_name": quote.supplier.supplier_name if quote.supplier else "",
                        "quantity_quoted": float(m.quantity),
                        "unit_price": float(m.unit_price),
                        "discount_pct": float(m.discount_pct),
                        "line_total": float(m.line_total),
                        "lead_time_days": m.lead_time_days,
                    })

            # Sort bids by unit_price ascending
            bids.sort(key=lambda b: b["unit_price"])
            min_price = bids[0]["unit_price"] if bids else 0.0
            max_price = bids[-1]["unit_price"] if bids else 0.0

            for idx, bid in enumerate(bids):
                bid["rank"] = idx + 1
                bid["is_lowest_price"] = (bid["unit_price"] == min_price) if bids else False

            items_matrix.append({
                "item_id": str(rfq_item.item_id),
                "item_code": rfq_item.item.item_code if rfq_item.item else "",
                "item_name": rfq_item.item.item_name if rfq_item.item else "",
                "required_qty": float(rfq_item.quantity),
                "bids": bids,
                "min_price": min_price,
                "max_price": max_price,
                "price_variance": (max_price - min_price) if bids else 0.0,
            })

        return {
            "rfq_id": str(rfq.rfq_id),
            "rfq_number": rfq.rfq_number,
            "status": rfq.status,
            "total_invited_suppliers": len(rfq.suppliers),
            "total_quotes_received": len(quotes),
            "quotations": overall_quotations,
            "items_matrix": items_matrix,
        }

    async def award_quotation_to_po(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        sq_id: uuid.UUID,
        po_number: str,
    ) -> PurchaseOrder:
        """Awards a supplier quote, generates a Purchase Order, and rejects competitors."""
        quote = await self.get_supplier_quotation(session, tenant_id, sq_id)
        if not quote:
            raise ValueError(f"Supplier Quotation {sq_id} not found.")

        # Update quotation status
        quote.status = "AWARDED"

        # If linked to RFQ, reject other quotations and mark RFQ completed
        if quote.rfq_id:
            other_quotes_stmt = select(SupplierQuotation).where(
                SupplierQuotation.tenant_id == tenant_id,
                SupplierQuotation.rfq_id == quote.rfq_id,
                SupplierQuotation.sq_id != quote.sq_id,
            )
            other_quotes = (await session.execute(other_quotes_stmt)).scalars().all()
            for oq in other_quotes:
                if oq.status != "AWARDED":
                    oq.status = "REJECTED"

            rfq = await self.get_rfq(session, tenant_id, quote.rfq_id)
            if rfq:
                rfq.status = "COMPLETED"

        # Generate Purchase Order
        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_number=po_number,
            supplier_id=quote.supplier_id,
            order_date=date.today(),
            currency=quote.currency,
            subtotal=quote.subtotal,
            tax_amount=quote.tax_amount,
            total_amount=quote.grand_total,
            status="SUBMITTED",
        )
        session.add(po)
        await session.flush()

        for it in quote.items:
            po_item = PurchaseOrderItem(
                tenant_id=tenant_id,
                po_id=po.po_id,
                item_id=it.item_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                line_total=it.line_total,
            )
            session.add(po_item)

        await session.flush()

        # Reload PO with lines
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item),
                selectinload(PurchaseOrder.supplier),
            )
            .where(PurchaseOrder.po_id == po.po_id)
        )
        return (await session.execute(stmt)).scalar_one()


sourcing_service = SourcingService()
