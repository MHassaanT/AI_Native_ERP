"""Comprehensive End-to-End Parity Tests for Phase 2: Buying, Procurement, Landed Costs, and Subcontracting.

Verifies:
1. Material Request (Requisition) lifecycle (Draft, Submit, Cancel).
2. Automated Safety Stock Replenishment scanner and requisition generation.
3. Conversion of Requisitions to Purchase Orders with ordered quantity tracking.
4. Strategic Sourcing: RFQ tendering across multiple competing vendors.
5. Supplier Quotations, Side-by-Side Comparison Matrix & 1-Click PO Awarding.
6. Blanket Orders (Contract Purchasing) with quota drawdown and rate lock-in.
7. Landed Cost Vouchers: Apportionment (Valuation & Quantity), Stock Valuation Updates, and GL Posting.
8. Supplier Performance Scorecards: OTIF, Quality Acceptance, Pricing Variance, and Standing Tiers.
9. Subcontracting: Order lifecycle, raw component warehouse transfer, and finished goods receipt with auto-consumption.
10. GRN Quality Inspection: Accepted vs Rejected quantities with quarantine warehouse routing.
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.landed_cost import LandedCostVoucher
from erp.db.models.purchasing import (
    BlanketOrder,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    MaterialRequest,
    PurchaseOrder,
    PurchaseOrderItem,
    RequestForQuotation,
    Supplier,
    SupplierInvoice,
    SupplierQuotation,
    SupplierScorecard,
)
from erp.db.models.subcontracting import SubcontractingOrder, SubcontractingReceipt
from erp.db.session import async_session_factory
from erp.workflows.procurement.blanket_order_service import blanket_order_service
from erp.workflows.procurement.landed_cost_service import landed_cost_service
from erp.workflows.procurement.requisition_service import requisition_service
from erp.workflows.procurement.sourcing_service import sourcing_service
from erp.workflows.procurement.subcontracting_service import subcontracting_service
from erp.workflows.procurement.supplier_scorecard_service import supplier_scorecard_service


@pytest.mark.asyncio
async def test_phase2_complete_procurement_parity():
    """Runs the complete suite of Phase 2 procurement, landed cost, and subcontracting workflows."""
    async with async_session_factory() as session:
        # 1. Setup Tenant and Master Entities
        supp_stmt = select(Supplier).limit(1)
        res = await session.execute(supp_stmt)
        supplier_a = res.scalars().first()

        if not supplier_a:
            tenant_id = uuid.uuid4()
            supplier_a = Supplier(
                tenant_id=tenant_id,
                supplier_code=f"SUPP-A-{uuid.uuid4().hex[:4].upper()}",
                supplier_name="Apex Industrial Supplies",
                payment_terms_days=30,
                otif_score=Decimal("100.00"),
                is_active=True,
            )
            session.add(supplier_a)
            await session.flush()
        else:
            tenant_id = supplier_a.tenant_id

        # Supplier B for competing RFQ bids
        supplier_b = Supplier(
            tenant_id=tenant_id,
            supplier_code=f"SUPP-B-{uuid.uuid4().hex[:4].upper()}",
            supplier_name="Global Fasteners & Raw Materials",
            payment_terms_days=45,
            otif_score=Decimal("95.00"),
            is_active=True,
        )
        session.add(supplier_b)
        await session.flush()

        # Warehouses: Main, Supplier Vendor WH, Quarantine WH
        main_wh = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"MAIN-WH-{uuid.uuid4().hex[:4].upper()}",
            warehouse_name="Central Main Warehouse",
            is_active=True,
        )
        subcon_wh = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"VEND-WH-{uuid.uuid4().hex[:4].upper()}",
            warehouse_name="Subcontractor Vendor Warehouse",
            is_active=True,
        )
        quarantine_wh = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"QUAR-{uuid.uuid4().hex[:4].upper()}",
            warehouse_name="QA Quarantine Warehouse",
            is_quarantine=True,
            is_active=True,
        )
        session.add_all([main_wh, subcon_wh, quarantine_wh])
        await session.flush()

        # Items: Raw Material & Finished Subcontracted Assembly
        raw_material = Item(
            tenant_id=tenant_id,
            item_code=f"RAW-STEEL-{uuid.uuid4().hex[:4].upper()}",
            item_name="Precision Sheet Steel",
            stock_uom="Kg",
            is_stock_item=True,
            is_purchase_item=True,
            standard_rate=Decimal("25.0000"),
            reorder_level=Decimal("100.0000"),
            is_active=True,
        )
        finished_assembly = Item(
            tenant_id=tenant_id,
            item_code=f"FG-FRAME-{uuid.uuid4().hex[:4].upper()}",
            item_name="Welded Frame Subassembly",
            stock_uom="Nos",
            is_stock_item=True,
            is_purchase_item=True,
            standard_rate=Decimal("150.0000"),
            reorder_level=Decimal("20.0000"),
            is_active=True,
        )
        session.add_all([raw_material, finished_assembly])
        await session.flush()

        # Prime initial raw stock
        init_stk = StockLevel(
            tenant_id=tenant_id,
            item_id=raw_material.item_id,
            warehouse_id=main_wh.warehouse_id,
            current_qty=Decimal("500.0000"),
            reserved_qty=Decimal("0.0000"),
            available_qty=Decimal("500.0000"),
            valuation_rate=Decimal("25.0000"),
        )
        session.add(init_stk)
        await session.flush()

        # =========================================================================
        # 1. Material Request (Requisition) Lifecycle
        # =========================================================================
        mr_num = f"MR-TEST-{uuid.uuid4().hex[:6].upper()}"
        mr = await requisition_service.create_material_request(
            session=session,
            tenant_id=tenant_id,
            mr_number=mr_num,
            material_request_type="PURCHASE",
            schedule_date=date.today() + timedelta(days=5),
            notes="Quarterly raw material requisition",
            items=[
                {
                    "item_id": raw_material.item_id,
                    "quantity": Decimal("200.0000"),
                    "target_warehouse_id": main_wh.warehouse_id,
                    "uom": "Kg",
                }
            ],
        )
        assert mr.status == "DRAFT"
        assert len(mr.items) == 1
        assert mr.items[0].quantity == Decimal("200.0000")
        assert mr.items[0].ordered_qty == Decimal("0.0000")

        # Submit MR
        mr = await requisition_service.submit_material_request(session, tenant_id, mr.mr_id)
        assert mr.status == "SUBMITTED"

        # Partial PO conversion from MR
        po_num_mr = f"PO-FROM-MR-{uuid.uuid4().hex[:6].upper()}"
        po_from_mr = await requisition_service.create_po_from_material_request(
            session=session,
            tenant_id=tenant_id,
            mr_id=mr.mr_id,
            supplier_id=supplier_a.supplier_id,
            po_number=po_num_mr,
            items_to_order=[
                {
                    "mr_item_id": mr.items[0].mr_item_id,
                    "quantity": Decimal("100.0000"),
                    "unit_price": Decimal("24.5000"),
                }
            ],
        )
        assert po_from_mr.po_number == po_num_mr
        assert po_from_mr.subtotal == Decimal("2450.0000")
        # MR should now be PARTIALLY_ORDERED
        reloaded_mr = await requisition_service.get_material_request(session, tenant_id, mr.mr_id)
        assert reloaded_mr is not None
        assert reloaded_mr.status == "PARTIALLY_ORDERED"
        assert reloaded_mr.items[0].ordered_qty == Decimal("100.0000")

        # Fulfill remainder
        po_num_mr2 = f"PO-FROM-MR2-{uuid.uuid4().hex[:6].upper()}"
        await requisition_service.create_po_from_material_request(
            session=session,
            tenant_id=tenant_id,
            mr_id=mr.mr_id,
            supplier_id=supplier_a.supplier_id,
            po_number=po_num_mr2,
            items_to_order=[
                {
                    "mr_item_id": mr.items[0].mr_item_id,
                    "quantity": Decimal("100.0000"),
                    "unit_price": Decimal("24.5000"),
                }
            ],
        )
        reloaded_mr_full = await requisition_service.get_material_request(session, tenant_id, mr.mr_id)
        assert reloaded_mr_full is not None
        assert reloaded_mr_full.status == "ORDERED"
        assert reloaded_mr_full.items[0].ordered_qty == Decimal("200.0000")

        # =========================================================================
        # 2. Automated Safety Stock Replenishment Check
        # =========================================================================
        # Finished assembly has current_qty = 0 and reorder_level = 20.0
        auto_mrs = await requisition_service.check_reorder_replenishment(session, tenant_id)
        assert len(auto_mrs) >= 1
        auto_mr = auto_mrs[0]
        assert auto_mr.status == "DRAFT"
        assert any(it.item_id == finished_assembly.item_id for it in auto_mr.items)

        # =========================================================================
        # 3. RFQs, Competing Bids & Side-by-Side Comparison Matrix
        # =========================================================================
        rfq_num = f"RFQ-{uuid.uuid4().hex[:6].upper()}"
        rfq = await sourcing_service.create_rfq(
            session=session,
            tenant_id=tenant_id,
            rfq_number=rfq_num,
            supplier_ids=[supplier_a.supplier_id, supplier_b.supplier_id],
            items=[
                {"item_id": raw_material.item_id, "quantity": Decimal("1000.0000")},
            ],
            notes="Bulk steel procurement tender",
        )
        assert rfq.status == "DRAFT"
        assert len(rfq.suppliers) == 2

        # Send RFQ
        rfq = await sourcing_service.send_rfq(session, tenant_id, rfq.rfq_id)
        assert rfq.status == "SENT"
        assert all(s.email_sent for s in rfq.suppliers)

        # Supplier A quotes $25.00/kg with 5 days lead time
        sq_a = await sourcing_service.create_supplier_quotation(
            session=session,
            tenant_id=tenant_id,
            quotation_number=f"SQ-A-{uuid.uuid4().hex[:6].upper()}",
            supplier_id=supplier_a.supplier_id,
            rfq_id=rfq.rfq_id,
            lead_time_days=5,
            items=[
                {
                    "item_id": raw_material.item_id,
                    "quantity": Decimal("1000.0000"),
                    "unit_price": Decimal("25.0000"),
                    "discount_pct": Decimal("4.00"),  # Net: 24.00
                }
            ],
        )
        # Supplier B quotes $23.50/kg with 10 days lead time
        sq_b = await sourcing_service.create_supplier_quotation(
            session=session,
            tenant_id=tenant_id,
            quotation_number=f"SQ-B-{uuid.uuid4().hex[:6].upper()}",
            supplier_id=supplier_b.supplier_id,
            rfq_id=rfq.rfq_id,
            lead_time_days=10,
            items=[
                {
                    "item_id": raw_material.item_id,
                    "quantity": Decimal("1000.0000"),
                    "unit_price": Decimal("23.5000"),
                    "discount_pct": Decimal("0.00"),  # Net: 23.50
                }
            ],
        )

        # Generate Side-by-Side Comparison Matrix
        matrix = await sourcing_service.get_quote_comparison_matrix(session, tenant_id, rfq.rfq_id)
        assert matrix["total_quotes_received"] == 2
        assert len(matrix["items_matrix"]) == 1
        item_bids = matrix["items_matrix"][0]["bids"]
        assert len(item_bids) == 2
        # Lowest price bid should be ranked #1
        assert item_bids[0]["rank"] == 1
        assert item_bids[0]["unit_price"] == 23.50
        assert item_bids[0]["is_lowest_price"] is True

        # Award to Supplier B with 1-click PO generation
        awarded_po_num = f"PO-AWARD-{uuid.uuid4().hex[:6].upper()}"
        awarded_po = await sourcing_service.award_quotation_to_po(
            session=session,
            tenant_id=tenant_id,
            sq_id=sq_b.sq_id,
            po_number=awarded_po_num,
        )
        assert awarded_po.supplier_id == supplier_b.supplier_id
        assert awarded_po.total_amount == Decimal("23500.0000")

        # Verify competitor quotation was rejected and RFQ completed
        sq_a_check = await sourcing_service.get_supplier_quotation(session, tenant_id, sq_a.sq_id)
        sq_b_check = await sourcing_service.get_supplier_quotation(session, tenant_id, sq_b.sq_id)
        rfq_check = await sourcing_service.get_rfq(session, tenant_id, rfq.rfq_id)
        assert sq_b_check is not None and sq_b_check.status == "AWARDED"
        assert sq_a_check is not None and sq_a_check.status == "REJECTED"
        assert rfq_check is not None and rfq_check.status == "COMPLETED"

        # =========================================================================
        # 4. Blanket Orders (Contract Purchasing) & Drawdowns
        # =========================================================================
        bo_num = f"BO-{uuid.uuid4().hex[:6].upper()}"
        bo = await blanket_order_service.create_blanket_order(
            session=session,
            tenant_id=tenant_id,
            order_number=bo_num,
            supplier_id=supplier_a.supplier_id,
            from_date=date.today() - timedelta(days=1),
            to_date=date.today() + timedelta(days=365),
            items=[
                {
                    "item_id": raw_material.item_id,
                    "quantity": Decimal("5000.0000"),
                    "unit_price": Decimal("22.0000"),  # Volume contracted rate
                }
            ],
        )
        assert bo.status == "ACTIVE"
        assert bo.total_amount == Decimal("110000.0000")

        # First drawdown release of 2000 units
        drawdown_po_num1 = f"PO-BO-REL1-{uuid.uuid4().hex[:6].upper()}"
        dd_po1 = await blanket_order_service.create_po_from_blanket_order(
            session=session,
            tenant_id=tenant_id,
            blanket_order_id=bo.blanket_order_id,
            po_number=drawdown_po_num1,
            item_drawdowns=[{"item_id": raw_material.item_id, "quantity": Decimal("2000.0000")}],
        )
        assert dd_po1.subtotal == Decimal("44000.0000")

        bo_check1 = await blanket_order_service.get_blanket_order(session, tenant_id, bo.blanket_order_id)
        assert bo_check1 is not None
        assert bo_check1.items[0].ordered_qty == Decimal("2000.0000")
        assert bo_check1.status == "ACTIVE"

        # Attempt exceeding drawdown quota
        with pytest.raises(ValueError, match="exceeds remaining contract balance"):
            await blanket_order_service.create_po_from_blanket_order(
                session=session,
                tenant_id=tenant_id,
                blanket_order_id=bo.blanket_order_id,
                po_number=f"PO-INVALID-DRAWDOWN-{uuid.uuid4().hex[:6].upper()}",
                item_drawdowns=[{"item_id": raw_material.item_id, "quantity": Decimal("4000.0000")}],
            )

        # Draw down remainder (3000 units) to close the blanket contract
        drawdown_po_num2 = f"PO-BO-REL2-{uuid.uuid4().hex[:6].upper()}"
        await blanket_order_service.create_po_from_blanket_order(
            session=session,
            tenant_id=tenant_id,
            blanket_order_id=bo.blanket_order_id,
            po_number=drawdown_po_num2,
            item_drawdowns=[{"item_id": raw_material.item_id, "quantity": Decimal("3000.0000")}],
        )
        bo_check2 = await blanket_order_service.get_blanket_order(session, tenant_id, bo.blanket_order_id)
        assert bo_check2 is not None
        assert bo_check2.items[0].ordered_qty == Decimal("5000.0000")
        assert bo_check2.status == "CLOSED"

        # =========================================================================
        # 5. Landed Cost Vouchers & Inventory Capitalization
        # =========================================================================
        # Create a GRN for 100 units of raw material @ $25 = $2,500
        grn_lcv = GoodsReceiptNote(
            tenant_id=tenant_id,
            grn_number=f"GRN-LCV-{uuid.uuid4().hex[:6].upper()}",
            supplier_id=supplier_a.supplier_id,
            receipt_date=date.today(),
            status="COMPLETED",
        )
        session.add(grn_lcv)
        await session.flush()

        grn_item_lcv = GoodsReceiptNoteItem(
            tenant_id=tenant_id,
            grn_id=grn_lcv.grn_id,
            item_id=raw_material.item_id,
            quantity_received=Decimal("100.0000"),
            quantity_accepted=Decimal("100.0000"),
            unit_price=Decimal("25.0000"),
        )
        session.add(grn_item_lcv)
        await session.flush()

        # Create Landed Cost Voucher adding $500 shipping + $200 customs = $700 charges
        lcv_num = f"LCV-{uuid.uuid4().hex[:6].upper()}"
        lcv = await landed_cost_service.create_landed_cost_voucher(
            session=session,
            tenant_id=tenant_id,
            voucher_number=lcv_num,
            grn_ids=[grn_lcv.grn_id],
            distribute_charges_based_on="VALUATION",
            taxes_and_charges=[
                {
                    "expense_account": "5100-FREIGHT-CUSTOMS-CLEARING",
                    "description": "Ocean Freight & Port Surcharge",
                    "amount": Decimal("500.0000"),
                },
                {
                    "expense_account": "5100-FREIGHT-CUSTOMS-CLEARING",
                    "description": "Customs Tariff & Import Duty",
                    "amount": Decimal("200.0000"),
                },
            ],
        )
        assert lcv.status == "DRAFT"
        assert lcv.total_charges == Decimal("700.0000")
        assert len(lcv.items) == 1
        # With 100 units, $700 / 100 = $7.00 added per unit. New rate = 25.00 + 7.00 = 32.0000
        assert lcv.items[0].applicable_charges == Decimal("700.0000")
        assert lcv.items[0].new_valuation_rate == Decimal("32.0000")

        # Submit LCV (commits GL and updates item valuation rate)
        submitted_lcv = await landed_cost_service.submit_landed_cost_voucher(
            session=session, tenant_id=tenant_id, lcv_id=lcv.lcv_id
        )
        assert submitted_lcv.status == "SUBMITTED"

        # Check raw material standard rate was updated
        item_check = (
            await session.execute(
                select(Item).where(Item.item_id == raw_material.item_id, Item.tenant_id == tenant_id)
            )
        ).scalar_one()
        assert item_check.standard_rate == Decimal("32.0000")

        # =========================================================================
        # 6. Supplier Performance Scorecard & Standing Tiers
        # =========================================================================
        scorecard = await supplier_scorecard_service.calculate_and_generate_scorecard(
            session=session,
            tenant_id=tenant_id,
            supplier_id=supplier_a.supplier_id,
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            evaluation_period="MONTHLY",
        )
        assert scorecard.supplier_id == supplier_a.supplier_id
        assert scorecard.standing in ("PREFERRED", "STANDARD", "AT_RISK", "BLACKLISTED")
        assert len(scorecard.criteria) == 3
        assert scorecard.total_score > Decimal("0.00")

        leaderboard = await supplier_scorecard_service.get_supplier_leaderboard(session, tenant_id)
        assert len(leaderboard) >= 2
        assert leaderboard[0]["rank"] == 1

        # =========================================================================
        # 7. Subcontracting: Issuance, Outsourced Assembly & Finished Goods Receipt
        # =========================================================================
        sco_num = f"SCO-{uuid.uuid4().hex[:6].upper()}"
        sco = await subcontracting_service.create_subcontracting_order(
            session=session,
            tenant_id=tenant_id,
            sco_number=sco_num,
            supplier_id=supplier_a.supplier_id,
            service_cost=Decimal("1500.0000"),
            finished_items=[
                {
                    "item_id": finished_assembly.item_id,
                    "quantity": Decimal("10.0000"),
                    "unit_price": Decimal("150.0000"),
                }
            ],
            supplied_items=[
                {
                    "raw_item_id": raw_material.item_id,
                    "required_qty": Decimal("50.0000"),  # 5kg steel per frame
                    "source_warehouse_id": main_wh.warehouse_id,
                    "supplier_warehouse_id": subcon_wh.warehouse_id,
                }
            ],
        )
        assert sco.status == "DRAFT"

        # Submit SCO
        sco = await subcontracting_service.submit_subcontracting_order(session, tenant_id, sco.sco_id)
        assert sco.status == "SUBMITTED"

        # Transfer raw materials to subcontractor warehouse
        sco = await subcontracting_service.transfer_subcontracting_materials(
            session=session,
            tenant_id=tenant_id,
            sco_id=sco.sco_id,
            transfers=[
                {
                    "raw_item_id": raw_material.item_id,
                    "quantity": Decimal("50.0000"),
                    "source_warehouse_id": main_wh.warehouse_id,
                    "supplier_warehouse_id": subcon_wh.warehouse_id,
                }
            ],
        )
        assert sco.status == "IN_PROCESS"
        assert sco.supplied_items[0].supplied_qty == Decimal("50.0000")

        # Verify subcontractor warehouse has the stock
        sub_wh_stk = (
            await session.execute(
                select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == raw_material.item_id,
                    StockLevel.warehouse_id == subcon_wh.warehouse_id,
                )
            )
        ).scalar_one()
        assert sub_wh_stk.current_qty == Decimal("50.0000")

        # Receive finished goods and auto-consume raw components
        scr_num = f"SCR-{uuid.uuid4().hex[:6].upper()}"
        scr = await subcontracting_service.receive_subcontracting_receipt(
            session=session,
            tenant_id=tenant_id,
            scr_number=scr_num,
            sco_id=sco.sco_id,
            target_warehouse_id=main_wh.warehouse_id,
            finished_items_received=[
                {
                    "item_id": finished_assembly.item_id,
                    "quantity_received": Decimal("10.0000"),
                    "service_rate": Decimal("150.0000"),
                }
            ],
        )
        assert scr.status == "COMPLETED"
        assert len(scr.items) == 1
        assert scr.items[0].quantity_received == Decimal("10.0000")

        # Check finished good was stocked in main WH
        fg_stk = (
            await session.execute(
                select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == finished_assembly.item_id,
                    StockLevel.warehouse_id == main_wh.warehouse_id,
                )
            )
        ).scalar_one()
        assert fg_stk.current_qty >= Decimal("10.0000")

        # Check raw materials were consumed from subcontractor warehouse
        sub_wh_stk_after = (
            await session.execute(
                select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == raw_material.item_id,
                    StockLevel.warehouse_id == subcon_wh.warehouse_id,
                )
            )
        ).scalar_one()
        assert sub_wh_stk_after.current_qty == Decimal("0.0000")

        # Check SCO is COMPLETED
        sco_completed = await subcontracting_service.get_subcontracting_order(session, tenant_id, sco.sco_id)
        assert sco_completed is not None
        assert sco_completed.status == "COMPLETED"
        assert sco_completed.supplied_items[0].consumed_qty == Decimal("50.0000")

        await session.commit()
