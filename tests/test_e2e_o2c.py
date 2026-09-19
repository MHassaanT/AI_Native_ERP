"""End-to-End Test Suite for Order-to-Cash (O2C) Business Cycle.

Verifies:
1. Ingest RFQ
2. Sales Quote Generation
3. Convert Quote to Sales Order & Stock Reservation
4. Delivery Fulfillment, Stock Deduction & Stock Ledger Entry
5. Sales Invoice Generation & GL Posting (Dr 1200-AR-CUSTOMERS / Cr 4000-SALES-REVENUE)
6. Bank Settlement Webhook, Semantic Matching & Invoice Settlement (Status PAID)
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
from erp.db.models.sales import (
    Customer,
    DeliveryNote,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
)



@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_order_to_cash_full_lifecycle():
    slug = f"o2c-{uuid.uuid4().hex[:6]}"
    email = f"o2c-admin@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 0: Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "O2C Aerospace Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordO2C123!",
                "full_name": "O2C Director",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Ingest RFQ via Inbound Email Webhook
        rfq_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "procurement@lockheed.com",
                "recipient": "rfq@company.internal",
                "subject": "RFQ Request: 10 units of Titanium Enclosure FG-ENCLOSURE-IP67",
                "body_text": "Please provide a formal quote for 10 units of FG-ENCLOSURE-IP67 with delivery by Q4.",
            },
            headers=headers,
        )
        assert rfq_res.status_code == 200, rfq_res.text
        rfq_data = rfq_res.json()
        assert rfq_data["status"] == "INGESTED"


        # Setup Customer, Warehouse, and Item in DB
        async with async_session_factory() as session:
            cust = Customer(
                tenant_id=tenant_id,
                customer_code=f"CUST-LOCKHEED-{uuid.uuid4().hex[:4]}",
                customer_name="Lockheed Aerospace",
                email="procurement@lockheed.com",
                credit_limit=Decimal("100000.0000"),
            )

            session.add(cust)

            item = Item(
                tenant_id=tenant_id,
                item_code="FG-ENCLOSURE-IP67",
                item_name="Titanium Enclosure IP67",
                standard_rate=Decimal("1200.0000"),
                is_active=True,
            )

            session.add(item)
            await session.flush()

            wh = (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.tenant_id == tenant_id,
                        Warehouse.is_active.is_(True),
                    )
                )
            ).scalars().first()
            assert wh is not None, "Warehouse should be provisioned"

            # Initial stock of 100 units
            stock = StockLevel(
                tenant_id=tenant_id,
                item_id=item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("100.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("100.0000"),
                valuation_rate=Decimal("1200.0000"),
            )
            session.add(stock)
            await session.commit()

            customer_id = cust.customer_id
            item_id = item.item_id
            wh_id = wh.warehouse_id

        # Step 2: Create Sales Quote
        quote_num = f"QT-{uuid.uuid4().hex[:6].upper()}"
        quote_res = await client.post(
            "/api/v1/commercial/quotes",
            json={
                "quotation_number": quote_num,
                "customer_id": str(customer_id),
                "quotation_date": date.today().isoformat(),
                "valid_until": date.today().isoformat(),
                "subtotal": "18000.0000",
                "tax_amount": "0.0000",
                "contribution_margin_pct": "33.33",
            },
            headers=headers,
        )
        assert quote_res.status_code == 201, quote_res.text
        quote_id = quote_res.json()["quotation_id"]


        # Step 3: Convert Quote to Sales Order (Reserves Stock)
        so_num = f"SO-{uuid.uuid4().hex[:6].upper()}"
        convert_res = await client.post(
            f"/api/v1/commercial/quotes/{quote_id}/convert-to-order",
            json={
                "order_number": so_num,
                "warehouse_id": str(wh_id),
                "items": [
                    {
                        "item_id": str(item_id),
                        "quantity": "10.0000",
                        "unit_price": "1800.0000",
                    }
                ],
            },
            headers=headers,
        )
        assert convert_res.status_code == 201, convert_res.text
        order_data = convert_res.json()
        order_id = order_data["order_id"]
        assert order_data["status"] == "CONFIRMED"

        # Verify DB: stock reserved
        async with async_session_factory() as session:
            stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == item_id,
                    )
                )
            ).scalar_one()
            assert stk.reserved_qty == Decimal("10.0000")
            assert stk.available_qty == Decimal("90.0000")

        # Step 4: Fulfill Order -> Delivery Note (Deducts Stock & Logs SLE)
        fulfill_res = await client.post(
            f"/api/v1/commercial/orders/{order_id}/fulfill",
            json={
                "warehouse_id": str(wh_id),
            },
            headers=headers,
        )
        assert fulfill_res.status_code == 201, fulfill_res.text
        dn_data = fulfill_res.json()
        dn_id = dn_data["delivery_note_id"]
        assert dn_data["status"] == "COMPLETED"

        # Verify DB: stock deducted and SLE recorded
        async with async_session_factory() as session:
            stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == item_id,
                    )
                )
            ).scalar_one()
            assert stk.current_qty == Decimal("90.0000")
            assert stk.reserved_qty == Decimal("0.0000")

            sle = (
                await session.execute(
                    select(StockLedgerEntry).where(
                        StockLedgerEntry.tenant_id == tenant_id,
                        StockLedgerEntry.source_document_id == uuid.UUID(dn_id),
                    )
                )
            ).scalar_one_or_none()
            assert sle is not None
            assert sle.actual_qty == Decimal("-10.0000")
            assert sle.source_document_type == "DELIVERY_NOTE"

        # Step 5: Create Sales Invoice & Post to GL
        inv_res = await client.post(
            f"/api/v1/commercial/delivery-notes/{dn_id}/create-invoice",
            json={},
            headers=headers,
        )
        assert inv_res.status_code == 201, inv_res.text
        inv_data = inv_res.json()
        inv_id = inv_data["invoice_id"]
        inv_number = inv_data["invoice_number"]
        assert inv_data["status"] == "ISSUED"

        # Verify DB: GeneralLedgerEntry posted (Dr AR-Customers / Cr Sales Revenue)
        async with async_session_factory() as session:
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == uuid.UUID(inv_id),
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2, "Should have 2 GL lines (balanced debit and credit)"
            total_debit = sum(line.debit_amount for line in gle_lines)
            total_credit = sum(line.credit_amount for line in gle_lines)
            assert total_debit == Decimal("18000.0000")
            assert total_credit == Decimal("18000.0000")

        # Step 6: Bank Settlement Webhook -> Reconcile & Mark Invoice PAID
        settle_res = await client.post(
            "/api/v1/webhooks/banking/settlement",
            json={
                "amount": 18000.0,
                "currency": "USD",
                "debtor_name": "Lockheed Aerospace",
                "debtor_account": "ACC-OPERATING-01",
                "remittance_reference": f"Payment for {inv_number}",
                "value_date": date.today().isoformat(),
            },
            headers=headers,
        )
        assert settle_res.status_code == 200, settle_res.text
        settle_data = settle_res.json()
        assert settle_data["status"] == "AUTO_MATCH_CONFIRMED"


        # Verify DB: SalesInvoice status is PAID
        async with async_session_factory() as session:
            sinv = (
                await session.execute(
                    select(SalesInvoice).where(
                        SalesInvoice.tenant_id == tenant_id,
                        SalesInvoice.invoice_id == uuid.UUID(inv_id),
                    )
                )
            ).scalar_one()
            assert sinv.status == "PAID", f"Expected invoice status PAID, got {sinv.status}"

