"""End-to-End Test Suite for Procure-to-Pay (P2P) Business Cycle.

Verifies:
1. Purchase Order Creation
2. Goods Receipt Note (GRN) with Line Items, Stock Level Increase & SLE
3. Supplier Invoice Creation with Line Items
4. Genuine 3-Way Match Execution & GL Posting (Dr 1300-RAW-MATERIALS / Cr 2100-AP-VENDORS)
5. 3-Way Match Discrepancy Detection & Rejection (No Rubber-Stamping)
"""

from datetime import date
from decimal import Decimal
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from erp.api.app import app
from erp.db.engine import async_engine
from erp.db.session import async_session_factory
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_procure_to_pay_full_lifecycle_and_discrepancy_detection():
    slug = f"p2p-{uuid.uuid4().hex[:6]}"
    email = f"p2p-admin@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 0: Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "P2P Precision Metals Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordP2P123!",
                "full_name": "Procurement Lead",
                "auto_provision": True,
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create Supplier
        supp_code = f"SUPP-ALCOA-{uuid.uuid4().hex[:4]}"
        supp_res = await client.post(
            "/api/v1/ap/suppliers",
            json={
                "supplier_code": supp_code,
                "supplier_name": "Alcoa Premium Aluminum",
                "tax_id": "US-TAX-889922",
                "currency": "USD",
                "payment_terms_days": 30,
                "otif_score": "98.50",
            },
            headers=headers,
        )
        assert supp_res.status_code == 201, supp_res.text
        supplier_id = uuid.UUID(supp_res.json()["supplier_id"])

        # Setup Raw Material Item and get primary warehouse
        async with async_session_factory() as session:
            item = Item(
                tenant_id=tenant_id,
                item_code="RAW-ALU-6061",
                item_name="Aluminum Billet 6061-T6",
                standard_rate=Decimal("150.0000"),
                is_active=True,
            )
            session.add(item)
            await session.flush()
            item_id = item.item_id

            wh = (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.tenant_id == tenant_id,
                        Warehouse.is_active.is_(True),
                    )
                )
            ).scalars().first()
            assert wh is not None, "Primary warehouse must be provisioned"
            wh_id = wh.warehouse_id
            await session.commit()

        # Step 2: Create Purchase Order (50 units @ $150.00)
        po_num = f"PO-{uuid.uuid4().hex[:6].upper()}"
        po_res = await client.post(
            "/api/v1/ap/purchase-orders",
            json={
                "po_number": po_num,
                "supplier_id": str(supplier_id),
                "order_date": date.today().isoformat(),
                "currency": "USD",
                "items": [
                    {
                        "item_id": str(item_id),
                        "quantity": "50.0000",
                        "unit_price": "150.0000",
                    }
                ],
            },
            headers=headers,
        )
        assert po_res.status_code == 201, po_res.text
        po_data = po_res.json()
        po_id = uuid.UUID(po_data["po_id"])
        assert po_data["status"] == "SUBMITTED"

        # Step 3: Create Goods Receipt Note (GRN) with Line Items
        grn_num = f"GRN-{uuid.uuid4().hex[:6].upper()}"
        grn_res = await client.post(
            "/api/v1/ap/goods-receipts",
            json={
                "grn_number": grn_num,
                "supplier_id": str(supplier_id),
                "po_id": str(po_id),
                "receipt_date": date.today().isoformat(),
                "warehouse_id": str(wh_id),
                "items": [
                    {
                        "item_id": str(item_id),
                        "quantity_received": "50.0000",
                        "unit_price": "150.0000",
                    }
                ],
            },
            headers=headers,
        )
        assert grn_res.status_code == 201, grn_res.text
        grn_data = grn_res.json()
        grn_id = uuid.UUID(grn_data["grn_id"])

        # Verify DB: GRN line item persisted, StockLevel increased, SLE written
        async with async_session_factory() as session:
            grn_items = (
                await session.execute(
                    select(GoodsReceiptNoteItem).where(
                        GoodsReceiptNoteItem.tenant_id == tenant_id,
                        GoodsReceiptNoteItem.grn_id == grn_id,
                    )
                )
            ).scalars().all()
            assert len(grn_items) == 1
            assert grn_items[0].quantity_received == Decimal("50.0000")

            stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == item_id,
                        StockLevel.warehouse_id == wh_id,
                    )
                )
            ).scalar_one()
            assert stk.current_qty == Decimal("50.0000")

            sle = (
                await session.execute(
                    select(StockLedgerEntry).where(
                        StockLedgerEntry.tenant_id == tenant_id,
                        StockLedgerEntry.source_document_id == grn_id,
                    )
                )
            ).scalar_one_or_none()
            assert sle is not None
            assert sle.actual_qty == Decimal("50.0000")
            assert sle.source_document_type == "GOODS_RECEIPT"

        # Step 4: Create Matching Supplier Invoice
        inv_num = f"INV-SUPP-{uuid.uuid4().hex[:6].upper()}"
        inv_res = await client.post(
            "/api/v1/ap/invoices",
            json={
                "invoice_number": inv_num,
                "supplier_id": str(supplier_id),
                "po_id": str(po_id),
                "grn_id": str(grn_id),
                "invoice_date": date.today().isoformat(),
                "currency": "USD",
                "subtotal": "7500.0000",
                "tax_amount": "0.0000",
                "items": [
                    {
                        "item_code": "RAW-ALU-6061",
                        "item_id": str(item_id),
                        "quantity": "50.0000",
                        "unit_price": "150.0000",
                    }
                ],
            },
            headers=headers,
        )
        assert inv_res.status_code == 201, inv_res.text
        inv_id = uuid.UUID(inv_res.json()["invoice_id"])

        # Verify DB: SupplierInvoiceItem persisted
        async with async_session_factory() as session:
            inv_items = (
                await session.execute(
                    select(SupplierInvoiceItem).where(
                        SupplierInvoiceItem.tenant_id == tenant_id,
                        SupplierInvoiceItem.invoice_id == inv_id,
                    )
                )
            ).scalars().all()
            assert len(inv_items) == 1
            assert inv_items[0].quantity == Decimal("50.0000")
            assert inv_items[0].unit_price == Decimal("150.0000")

        # Step 5: Execute 3-Way Match (Should MATCH and post to GL)
        match_res = await client.post(
            f"/api/v1/ap/match/{inv_id}",
            headers=headers,
        )
        assert match_res.status_code == 200, match_res.text
        match_data = match_res.json()
        assert match_data["is_matched"] is True
        assert match_data["matching_status"] == "MATCHED"
        assert match_data["tolerance_summary"]["is_fully_matched"] is True
        assert match_data["ledger_result"] is not None
        assert match_data["dispute_notice"] is None

        # Verify DB: GL Entry posted (Dr 1300-RAW-MATERIALS / Cr 2100-AP-VENDORS)
        async with async_session_factory() as session:
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == inv_id,
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2, "GL should have balanced Dr and Cr legs"
            total_debit = sum(line.debit_amount for line in gle_lines)
            total_credit = sum(line.credit_amount for line in gle_lines)
            assert total_debit == Decimal("7500.0000")
            assert total_credit == Decimal("7500.0000")

        # Step 6: Test Discrepancy Detection (Negative Test - Price Discrepancy)
        # Create second PO for 20 units @ $150.00 ($3000.00 total)
        po2_num = f"PO2-{uuid.uuid4().hex[:6].upper()}"
        po2_res = await client.post(
            "/api/v1/ap/purchase-orders",
            json={
                "po_number": po2_num,
                "supplier_id": str(supplier_id),
                "order_date": date.today().isoformat(),
                "currency": "USD",
                "items": [
                    {
                        "item_id": str(item_id),
                        "quantity": "20.0000",
                        "unit_price": "150.0000",
                    }
                ],
            },
            headers=headers,
        )
        po2_id = uuid.UUID(po2_res.json()["po_id"])

        # Create GRN for 20 units
        grn2_num = f"GRN2-{uuid.uuid4().hex[:6].upper()}"
        grn2_res = await client.post(
            "/api/v1/ap/goods-receipts",
            json={
                "grn_number": grn2_num,
                "supplier_id": str(supplier_id),
                "po_id": str(po2_id),
                "receipt_date": date.today().isoformat(),
                "warehouse_id": str(wh_id),
                "items": [
                    {
                        "item_id": str(item_id),
                        "quantity_received": "20.0000",
                        "unit_price": "150.0000",
                    }
                ],
            },
            headers=headers,
        )
        grn2_id = uuid.UUID(grn2_res.json()["grn_id"])

        # Create Discrepant Invoice: Invoiced @ $220.00 instead of $150.00 (46.7% price hike)
        inv2_num = f"INV-DISCREPANT-{uuid.uuid4().hex[:6].upper()}"
        inv2_res = await client.post(
            "/api/v1/ap/invoices",
            json={
                "invoice_number": inv2_num,
                "supplier_id": str(supplier_id),
                "po_id": str(po2_id),
                "grn_id": str(grn2_id),
                "invoice_date": date.today().isoformat(),
                "currency": "USD",
                "subtotal": "4400.0000",
                "tax_amount": "0.0000",
                "items": [
                    {
                        "item_code": "RAW-ALU-6061",
                        "item_id": str(item_id),
                        "quantity": "20.0000",
                        "unit_price": "220.0000",
                    }
                ],
            },
            headers=headers,
        )
        inv2_id = uuid.UUID(inv2_res.json()["invoice_id"])

        # Execute 3-Way Match on discrepant invoice
        match2_res = await client.post(
            f"/api/v1/ap/match/{inv2_id}",
            headers=headers,
        )
        assert match2_res.status_code == 200, match2_res.text
        match2_data = match2_res.json()
        assert match2_data["is_matched"] is False, "Discrepant invoice should NOT match"
        assert match2_data["matching_status"] in ["DISCREPANCY", "DISPUTED"]
        assert match2_data["tolerance_summary"]["is_fully_matched"] is False
        assert len(match2_data["tolerance_summary"]["discrepancies"]) > 0
        assert match2_data["ledger_result"] is None, "No GL entry should be committed for discrepant invoice"
        assert match2_data["dispute_notice"] is not None, "Vendor dispute notice should be generated"


