"""Supplier Scorecard, OTIF, Quality Acceptance, and Standing Service."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
    SupplierScorecard,
    SupplierScorecardCriteria,
)

logger = logging.getLogger(__name__)


class SupplierScorecardService:
    """Core domain logic for Vendor Performance Scorecards, OTIF, and Quality Ratings."""

    async def calculate_and_generate_scorecard(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID,
        period_start: date,
        period_end: date,
        evaluation_period: str = "MONTHLY",
    ) -> SupplierScorecard:
        """Calculates OTIF, Quality, and Pricing variance metrics for a supplier and creates a scorecard."""
        supp_stmt = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.supplier_id == supplier_id,
        )
        supplier = (await session.execute(supp_stmt)).scalar_one_or_none()
        if not supplier:
            raise ValueError(f"Supplier {supplier_id} not found.")

        # 1. Evaluate OTIF (On-Time In-Full)
        # Look up POs in date range
        po_stmt = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.order_date >= period_start,
                PurchaseOrder.order_date <= period_end,
            )
        )
        pos = (await session.execute(po_stmt)).scalars().all()

        # Look up GRNs in date range
        grn_stmt = (
            select(GoodsReceiptNote)
            .options(selectinload(GoodsReceiptNote.items))
            .where(
                GoodsReceiptNote.tenant_id == tenant_id,
                GoodsReceiptNote.supplier_id == supplier_id,
                GoodsReceiptNote.receipt_date >= period_start,
                GoodsReceiptNote.receipt_date <= period_end,
            )
        )
        grns = (await session.execute(grn_stmt)).scalars().all()

        # Compute OTIF: ratio of fulfilled PO quantities vs ordered
        total_ordered_qty = sum(
            (sum((it.quantity for it in po.items), Decimal("0.0000")) for po in pos),
            Decimal("0.0000"),
        )
        total_received_qty = sum(
            (sum((it.quantity_received for it in grn.items), Decimal("0.0000")) for grn in grns),
            Decimal("0.0000"),
        )

        if total_ordered_qty > Decimal("0.0000"):
            raw_otif = min(Decimal("100.00"), (total_received_qty / total_ordered_qty) * Decimal("100.00"))
            otif_score = raw_otif.quantize(Decimal("0.01"))
        else:
            otif_score = supplier.otif_score or Decimal("100.00")

        # 2. Evaluate Quality Score (Acceptance vs Rejection in GRNs)
        total_accepted = Decimal("0.0000")
        total_inspected = Decimal("0.0000")

        for grn in grns:
            for it in grn.items:
                acc = it.quantity_accepted if (it.quantity_accepted is not None and it.quantity_accepted > 0) else it.quantity_received
                rej = it.quantity_rejected if it.quantity_rejected is not None else Decimal("0.0000")
                total_accepted += acc
                total_inspected += (acc + rej)

        if total_inspected > Decimal("0.0000"):
            quality_score = ((total_accepted / total_inspected) * Decimal("100.00")).quantize(Decimal("0.01"))
        else:
            quality_score = Decimal("100.00")

        # 3. Evaluate Pricing Score (Invoice variance from purchase orders)
        inv_stmt = select(SupplierInvoice).where(
            SupplierInvoice.tenant_id == tenant_id,
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.invoice_date >= period_start,
            SupplierInvoice.invoice_date <= period_end,
        )
        invoices = (await session.execute(inv_stmt)).scalars().all()

        if invoices:
            total_variance = sum((abs(inv.variance_percentage) for inv in invoices), Decimal("0.0000"))
            avg_variance = total_variance / Decimal(len(invoices))
            pricing_score = max(Decimal("0.00"), Decimal("100.00") - avg_variance).quantize(Decimal("0.01"))
        else:
            pricing_score = Decimal("100.00")

        # 4. Total Score & Standing Calculation
        # Weights: OTIF = 40%, Quality = 40%, Pricing = 20%
        otif_weight = Decimal("40.00")
        quality_weight = Decimal("40.00")
        pricing_weight = Decimal("20.00")

        otif_weighted = (otif_score * otif_weight / Decimal("100.00")).quantize(Decimal("0.01"))
        quality_weighted = (quality_score * quality_weight / Decimal("100.00")).quantize(Decimal("0.01"))
        pricing_weighted = (pricing_score * pricing_weight / Decimal("100.00")).quantize(Decimal("0.01"))

        total_score = otif_weighted + quality_weighted + pricing_weighted

        # Determine standing tier:
        # PREFERRED >= 85
        # STANDARD >= 70
        # AT_RISK >= 50
        # BLACKLISTED < 50
        prevent_pos = False
        if total_score >= Decimal("85.00"):
            standing = "PREFERRED"
        elif total_score >= Decimal("70.00"):
            standing = "STANDARD"
        elif total_score >= Decimal("50.00"):
            standing = "AT_RISK"
        else:
            standing = "BLACKLISTED"
            prevent_pos = True

        scorecard = SupplierScorecard(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            evaluation_period=evaluation_period.upper(),
            period_start=period_start,
            period_end=period_end,
            otif_score=otif_score,
            quality_score=quality_score,
            pricing_score=pricing_score,
            total_score=total_score,
            standing=standing,
            prevent_pos_flag=prevent_pos,
        )
        session.add(scorecard)
        await session.flush()

        # Add criteria items
        c1 = SupplierScorecardCriteria(
            tenant_id=tenant_id,
            scorecard_id=scorecard.scorecard_id,
            criteria_name="On-Time In-Full Delivery (OTIF)",
            weight=otif_weight,
            raw_score=otif_score,
            weighted_score=otif_weighted,
        )
        c2 = SupplierScorecardCriteria(
            tenant_id=tenant_id,
            scorecard_id=scorecard.scorecard_id,
            criteria_name="Material Quality & Receipt Acceptance",
            weight=quality_weight,
            raw_score=quality_score,
            weighted_score=quality_weighted,
        )
        c3 = SupplierScorecardCriteria(
            tenant_id=tenant_id,
            scorecard_id=scorecard.scorecard_id,
            criteria_name="Pricing Accuracy & Low Variance",
            weight=pricing_weight,
            raw_score=pricing_score,
            weighted_score=pricing_weighted,
        )
        session.add_all([c1, c2, c3])

        # Update supplier master with latest OTIF
        supplier.otif_score = otif_score

        await session.flush()
        return await self.get_scorecard(session, tenant_id, scorecard.scorecard_id)  # type: ignore

    async def get_scorecard(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        scorecard_id: uuid.UUID,
    ) -> SupplierScorecard | None:
        """Fetches scorecard with criteria breakdown and supplier info."""
        stmt = (
            select(SupplierScorecard)
            .options(
                selectinload(SupplierScorecard.criteria),
                selectinload(SupplierScorecard.supplier),
            )
            .where(
                SupplierScorecard.tenant_id == tenant_id,
                SupplierScorecard.scorecard_id == scorecard_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_scorecards(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID | None = None,
        standing: str | None = None,
    ) -> list[SupplierScorecard]:
        """Lists scorecards."""
        stmt = (
            select(SupplierScorecard)
            .options(
                selectinload(SupplierScorecard.criteria),
                selectinload(SupplierScorecard.supplier),
            )
            .where(SupplierScorecard.tenant_id == tenant_id)
        )
        if supplier_id:
            stmt = stmt.where(SupplierScorecard.supplier_id == supplier_id)
        if standing:
            stmt = stmt.where(SupplierScorecard.standing == standing.upper())
        stmt = stmt.order_by(SupplierScorecard.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_supplier_leaderboard(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Retrieves performance leaderboard across all active suppliers."""
        supp_stmt = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.is_active == True,
        )
        suppliers = (await session.execute(supp_stmt)).scalars().all()

        leaderboard = []
        for s in suppliers:
            # Fetch latest scorecard
            sc_stmt = (
                select(SupplierScorecard)
                .where(
                    SupplierScorecard.tenant_id == tenant_id,
                    SupplierScorecard.supplier_id == s.supplier_id,
                )
                .order_by(SupplierScorecard.period_end.desc())
                .limit(1)
            )
            latest_sc = (await session.execute(sc_stmt)).scalar_one_or_none()

            leaderboard.append({
                "supplier_id": str(s.supplier_id),
                "supplier_code": s.supplier_code,
                "supplier_name": s.supplier_name,
                "otif_score": float(s.otif_score or 100.0),
                "quality_score": float(latest_sc.quality_score) if latest_sc else 100.0,
                "pricing_score": float(latest_sc.pricing_score) if latest_sc else 100.0,
                "total_score": float(latest_sc.total_score) if latest_sc else float(s.otif_score or 100.0),
                "standing": latest_sc.standing if latest_sc else ("PREFERRED" if (s.otif_score or 100) >= 85 else "STANDARD"),
                "prevent_pos_flag": latest_sc.prevent_pos_flag if latest_sc else False,
                "last_evaluated": str(latest_sc.period_end) if latest_sc else None,
            })

        # Rank by total_score descending
        leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
        for idx, entry in enumerate(leaderboard):
            entry["rank"] = idx + 1

        return leaderboard


supplier_scorecard_service = SupplierScorecardService()
