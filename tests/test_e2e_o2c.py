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


@pytest.mark.asyncio
async def test_autonomous_email_order_fulfillment_lifecycle():
    """Verifies:
    1. System notifications (Google OAuth alerts) are filtered out with ZERO spurious DAGs created.
    2. Real customer Purchase Order emails are classified as CUSTOMER_ORDER.
    3. Multi-agent DAG automatically checks warehouse stock availability.
    4. Auto-provisions Customer, Confirmed Sales Order, and reserves inventory.
    5. Fulfills Delivery Note, deducts physical inventory, records StockLedgerEntry, issues Sales Invoice, and posts GL double entries.
    6. Dispatches order confirmation without human intervention.
    """
    import asyncio
    from erp.orchestration.orchestrator import chief_orchestrator

    slug = f"auto-ord-{uuid.uuid4().hex[:6]}"
    email = f"ops@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Autonomous Logistics Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordAuto123!",
                "full_name": "Operations Lead",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Filter Google OAuth / System Security Alert Email
        sys_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "Google <no-reply@accounts.google.com>",
                "recipient": "admin@company.internal",
                "subject": "Security alert: You allowed ai-native-erp-rho.vercel.app access to some of your Google Account data",
                "body_text": "If you didn't grant access, you should check your security activity. Google Community Team.",
            },
            headers=headers,
        )
        assert sys_res.status_code == 200, sys_res.text
        sys_data = sys_res.json()
        assert sys_data["status"] == "FILTERED"
        assert sys_data["intent"] == "SYSTEM_NOTIFICATION"
        assert sys_data["dag_id"] is None
        assert sys_data["subtasks_spawned"] == 0

        # Seed catalog item & stock for tenant
        async with async_session_factory() as session:
            wh = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-APEX-01",
                warehouse_name="Apex Logistics Center",
                is_active=True,
            )
            session.add(wh)
            await session.flush()

            item = Item(
                tenant_id=tenant_id,
                item_code="FG-ENCLOSURE-IP67",
                item_name="Industrial FG-ENCLOSURE-IP67",
                standard_rate=Decimal("1200.0000"),
                is_active=True,
            )
            session.add(item)
            await session.flush()

            stk = StockLevel(
                tenant_id=tenant_id,
                item_id=item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("100.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("100.0000"),
                valuation_rate=Decimal("1200.0000"),
            )
            session.add(stk)
            await session.commit()

        # Step 2: Inbound Commercial Customer Purchase Order Email
        order_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "procurement@apex-defense.com",
                "recipient": "orders@company.internal",
                "subject": "Purchase Order PO-APEX-9001 for 15 units FG-ENCLOSURE-IP67",
                "body_text": "Please accept our Purchase Order PO-APEX-9001 for 15 units of FG-ENCLOSURE-IP67 at $1200/unit. Prompt delivery requested.",
            },
            headers=headers,
        )
        assert order_res.status_code == 200, order_res.text
        order_data = order_res.json()
        assert order_data["status"] == "INGESTED"
        assert order_data["intent"] == "CUSTOMER_ORDER"
        dag_id = order_data["dag_id"]
        assert dag_id is not None
        assert order_data["subtasks_spawned"] == 5

        # Wait for the background DAG execution to complete
        dag = chief_orchestrator.get_dag(dag_id)
        assert dag is not None

        for _ in range(30):
            if dag.is_finished():
                break
            await asyncio.sleep(0.3)

        assert dag.is_finished(), f"DAG {dag_id} did not finish within timeout"

        # Verify DAG state via GET endpoint
        dag_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert dag_res.status_code == 200
        dag_details = dag_res.json()
        assert dag_details["status"] == "COMPLETED"

        nodes = {n["name"]: n for n in dag_details["nodes"]}

        # 1. Extraction node
        assert "Extract Order & Buyer Entity" in nodes
        extract_out = nodes["Extract Order & Buyer Entity"]["output_result"]
        assert extract_out["intent"] == "CUSTOMER_ORDER"
        assert extract_out["po_number"] == "PO-APEX-9001"

        # 2. Stock Availability Check
        assert "Check Inventory & Stock Availability" in nodes
        stock_out = nodes["Check Inventory & Stock Availability"]["output_result"]
        assert stock_out["is_in_stock"] is True
        assert stock_out["fulfillment_status"] == "STOCK_AVAILABLE_READY_TO_FULFILL"

        # 3. Customer & Sales Order Auto-Provisioning
        assert "Auto-Provision Customer & Sales Order" in nodes
        prov_out = nodes["Auto-Provision Customer & Sales Order"]["output_result"]
        assert prov_out["status"] == "CONFIRMED"
        assert prov_out["order_number"] == "SO-APEX-9001"
        assert prov_out["stock_reserved"] == 15.0

        # 4. Delivery & Financial Controller GL Posting
        assert "Fulfill Delivery & Post Invoice to Ledger" in nodes
        fin_out = nodes["Fulfill Delivery & Post Invoice to Ledger"]["output_result"]
        assert fin_out["delivery_note_number"] == "DN-SO-APEX-9001"
        assert fin_out["invoice_number"] == "INV-APEX-9001"
        assert fin_out["general_ledger_status"] == "COMMITTED_AR_AND_REVENUE"

        # 5. Outbound Confirmation
        assert "Dispatch Order Confirmation & Invoice" in nodes
        disp_out = nodes["Dispatch Order Confirmation & Invoice"]["output_result"]
        assert disp_out["confirmation_dispatched"] is True

        # Verify Database Records
        async with async_session_factory() as session:
            # Verify Customer created
            cust = (
                await session.execute(
                    select(Customer).where(
                        Customer.tenant_id == tenant_id,
                        Customer.email == "procurement@apex-defense.com",
                    )
                )
            ).scalar_one_or_none()
            assert cust is not None

            # Verify Sales Order CONFIRMED
            so = (
                await session.execute(
                    select(SalesOrder).where(
                        SalesOrder.tenant_id == tenant_id,
                        SalesOrder.order_number == "SO-APEX-9001",
                    )
                )
            ).scalar_one_or_none()
            assert so is not None
            assert so.status == "CONFIRMED"

            # Verify Delivery Note COMPLETED
            dn = (
                await session.execute(
                    select(DeliveryNote).where(
                        DeliveryNote.tenant_id == tenant_id,
                        DeliveryNote.delivery_note_number == "DN-SO-APEX-9001",
                    )
                )
            ).scalar_one_or_none()
            assert dn is not None
            assert dn.status == "COMPLETED"

            # Verify Sales Invoice ISSUED
            inv = (
                await session.execute(
                    select(SalesInvoice).where(
                        SalesInvoice.tenant_id == tenant_id,
                        SalesInvoice.invoice_number == "INV-APEX-9001",
                    )
                )
            ).scalar_one_or_none()
            assert inv is not None
            assert inv.status == "ISSUED"

            # Verify General Ledger Entries
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == inv.invoice_id,
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2
            ar_line = next(l for l in gle_lines if l.account_code == "1200-AR-CUSTOMERS")
            rev_line = next(l for l in gle_lines if l.account_code == "4000-SALES-REVENUE")
            assert ar_line.debit_amount == Decimal("18000.0000")
            assert rev_line.credit_amount == Decimal("18000.0000")


@pytest.mark.asyncio
async def test_autonomous_email_order_shortage_backorder_lifecycle():
    """Verifies that when customer orders more quantity than available in warehouse:
    1. Node 2 flags shortage (is_in_stock = False).
    2. Node 3 creates SalesOrder with status BACKORDERED.
    3. Node 4 holds fulfillment without shipping or generating invoice.
    4. Node 5 dispatches an automated Backorder Notification email to the buyer detailing lead time.
    5. The notification is recorded in the sent mailbox.
    """
    import asyncio
    from erp.events.email_gateway import mailbox
    from erp.orchestration.orchestrator import chief_orchestrator

    slug = f"shortage-{uuid.uuid4().hex[:6]}"
    email = f"supply@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Heavy Machinery Supply Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordShort123!",
                "full_name": "Supply Manager",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Seed catalog with 100 units of FG-ENCLOSURE-IP67
        async with async_session_factory() as session:
            wh = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-TURBINE-01",
                warehouse_name="Turbine Supply Hub",
                is_active=True,
            )
            session.add(wh)
            await session.flush()

            item = Item(
                tenant_id=tenant_id,
                item_code="FG-ENCLOSURE-IP67",
                item_name="Industrial FG-ENCLOSURE-IP67",
                standard_rate=Decimal("1200.0000"),
                is_active=True,
            )
            session.add(item)
            await session.flush()

            stk = StockLevel(
                tenant_id=tenant_id,
                item_id=item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("100.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("100.0000"),
                valuation_rate=Decimal("1200.0000"),
            )
            session.add(stk)
            await session.commit()

        # Customer sends PO for 250 units (warehouse has 100 units)
        order_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "purchasing@turbine-dynamics.com",
                "recipient": "orders@company.internal",
                "subject": "Purchase Order PO-TURBINE-550 for 250 units FG-ENCLOSURE-IP67",
                "body_text": "Please process our firm Purchase Order PO-TURBINE-550 for 250 units of FG-ENCLOSURE-IP67. Delivery needed urgently.",
            },
            headers=headers,
        )
        assert order_res.status_code == 200, order_res.text
        dag_id = order_res.json()["dag_id"]

        dag = chief_orchestrator.get_dag(dag_id)
        assert dag is not None

        # Wait for DAG execution
        for _ in range(30):
            if dag.is_finished():
                break
            await asyncio.sleep(0.3)

        assert dag.is_finished(), f"DAG {dag_id} did not finish within timeout"

        dag_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert dag_res.status_code == 200
        dag_details = dag_res.json()
        assert dag_details["status"] == "COMPLETED"

        nodes = {n["name"]: n for n in dag_details["nodes"]}

        # 1. Stock check flagged shortage
        stock_out = nodes["Check Inventory & Stock Availability"]["output_result"]
        assert stock_out["is_in_stock"] is False
        assert stock_out["fulfillment_status"] == "SHORTAGE_BACKORDER_TRIGGERED"
        assert stock_out["requested_qty"] == 250.0

        # 2. Sales Order marked BACKORDERED
        prov_out = nodes["Auto-Provision Customer & Sales Order"]["output_result"]
        assert prov_out["status"] == "BACKORDERED"
        assert prov_out["stock_reserved"] == 0.0

        # 3. Delivery & Invoicing held
        fin_out = nodes["Fulfill Delivery & Post Invoice to Ledger"]["output_result"]
        assert fin_out["delivery_note_number"] is None
        assert fin_out["invoice_number"] is None
        assert fin_out["fulfillment_status"] == "SHORTAGE_BACKORDER_HELD"

        # 4. Outbound shortage notification sent to customer
        disp_out = nodes["Dispatch Order Confirmation & Invoice"]["output_result"]
        assert disp_out["confirmation_dispatched"] is True
        assert disp_out["email_type"] == "INVENTORY_SHORTAGE_NOTIFICATION"
        assert disp_out["stock_status"] == "SHORTAGE_BACKORDERED"
        assert disp_out["recipient"] == "purchasing@turbine-dynamics.com"

        # 5. Verify email recorded in sent mailbox
        sent_emails = mailbox.get_sent(str(tenant_id))
        shortage_email = next((m for m in sent_emails if m.recipient == "purchasing@turbine-dynamics.com"), None)
        assert shortage_email is not None
        assert "Inventory Backorder" in shortage_email.subject
        assert "insufficient" in shortage_email.body.lower()


@pytest.mark.asyncio
async def test_gemini_email_order_catalog_matching_fulfillment():
    """Verifies that when a customer emails an order for an available catalog item (e.g. CHASHM-001):
    1. Gemini/order agent matches CHASHM-001 from tenant catalog.
    2. Pulls real unit price ($10.00) and confirms stock (500 available >= 20 requested).
    3. Provisions Sales Order for $200.00 total (20 * $10.00), NOT $24,000!
    4. Delivers stock and posts $200.00 to General Ledger.
    5. Dispatches official PDF Sales Invoice for CHASHM-001 to the customer.
    """
    import asyncio
    from erp.events.email_gateway import mailbox
    from erp.orchestration.orchestrator import chief_orchestrator

    slug = f"chashm-pass-{uuid.uuid4().hex[:6]}"
    email = f"sales@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Chashm Pvt Ltd",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordChashm123!",
                "full_name": "Chashm Admin",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Seed tenant warehouse and catalog items: CHASHM-001 ($10.00, 500 stock) and CHASHM ($5.00, 500 stock)
        async with async_session_factory() as session:
            wh = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-CHASHM-01",
                warehouse_name="Chashm Primary Hub",
                is_active=True,
            )
            session.add(wh)
            await session.flush()

            sensor_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM-001",
                item_name="Wall Mounted Sensor",
                standard_rate=Decimal("10.0000"),
                is_active=True,
            )
            relay_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM",
                item_name="Relay based Fan Regulator",
                standard_rate=Decimal("5.0000"),
                is_active=True,
            )
            session.add_all([sensor_item, relay_item])
            await session.flush()

            # Stock 500 units of each
            sensor_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=sensor_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("10.0000"),
            )
            relay_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=relay_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("5.0000"),
            )
            session.add_all([sensor_stock, relay_stock])
            await session.commit()

        # Customer sends email ordering 20 pieces of CHASHM-001
        order_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "Hassaan Tahir <misterhassan58@gmail.com>",
                "recipient": "orders@chashm.internal",
                "subject": "Order for Chashm",
                "body_text": "Hi, I want to order 20 pieces of CHASHM-001. Hassaan Tahir",
            },
            headers=headers,
        )
        assert order_res.status_code == 200, order_res.text
        dag_id = order_res.json()["dag_id"]

        dag = chief_orchestrator.get_dag(dag_id)
        assert dag is not None

        # Wait for DAG execution
        for _ in range(30):
            if dag.is_finished():
                break
            await asyncio.sleep(0.3)

        assert dag.is_finished(), f"DAG {dag_id} did not finish within timeout"

        dag_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert dag_res.status_code == 200
        dag_details = dag_res.json()
        assert dag_details["status"] == "COMPLETED"

        nodes = {n["name"]: n for n in dag_details["nodes"]}

        # 1. Verify Node 1 matched catalog item CHASHM-001
        extract_out = nodes["Extract Order & Buyer Entity"]["output_result"]
        assert extract_out["requested_sku"] == "CHASHM-001"
        assert extract_out["quantity"] == 20.0
        assert extract_out["target_unit_price"] == 10.0
        assert extract_out["item_found_in_catalog"] is True

        # 2. Verify Node 2 verified stock
        stock_out = nodes["Check Inventory & Stock Availability"]["output_result"]
        assert stock_out["is_in_stock"] is True
        assert stock_out["fulfillment_status"] == "STOCK_AVAILABLE_READY_TO_FULFILL"

        # 3. Verify Node 3 created Sales Order for $200.00 (NOT $24,000!)
        prov_out = nodes["Auto-Provision Customer & Sales Order"]["output_result"]
        assert prov_out["status"] == "CONFIRMED"
        assert prov_out["order_total"] == 200.0
        assert prov_out["target_unit_price"] == 10.0

        # 4. Verify Node 4 fulfilled and invoiced $200.00
        fin_out = nodes["Fulfill Delivery & Post Invoice to Ledger"]["output_result"]
        assert fin_out["invoice_number"] is not None
        assert fin_out["invoice_amount"] == 200.0
        assert fin_out["gl_posted"] is True

        # 5. Verify Node 5 dispatched email with invoice
        disp_out = nodes["Dispatch Order Confirmation & Invoice"]["output_result"]
        assert disp_out["confirmation_dispatched"] is True
        assert disp_out["email_type"] == "SALES_INVOICE_DISPATCH"
        assert disp_out["invoice_amount"] == 200.0
        assert disp_out["recipient"] == "misterhassan58@gmail.com"

        # 6. Verify Database State
        async with async_session_factory() as session:
            so = (
                await session.execute(
                    select(SalesOrder).where(
                        SalesOrder.tenant_id == tenant_id,
                        SalesOrder.order_number == prov_out["order_number"],
                    )
                )
            ).scalar_one_or_none()
            assert so is not None
            assert so.total_amount == Decimal("200.0000")

            inv = (
                await session.execute(
                    select(SalesInvoice).where(
                        SalesInvoice.tenant_id == tenant_id,
                        SalesInvoice.invoice_number == fin_out["invoice_number"],
                    )
                )
            ).scalar_one_or_none()
            assert inv is not None
            assert inv.total_amount == Decimal("200.0000")

            # Verify GL entries are exactly $200.00
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == inv.invoice_id,
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2
            ar_line = next(l for l in gle_lines if l.account_code == "1200-AR-CUSTOMERS")
            rev_line = next(l for l in gle_lines if l.account_code == "4000-SALES-REVENUE")
            assert ar_line.debit_amount == Decimal("200.0000")
            assert rev_line.credit_amount == Decimal("200.0000")


@pytest.mark.asyncio
async def test_gemini_email_order_unavailable_item_recommendation():
    """Verifies that when a customer emails ordering an unavailable SKU (e.g. CHASHM-002):
    1. Gemini/order agent detects CHASHM-002 does NOT exist in catalog.
    2. Does NOT create fake items or fake stock levels.
    3. Holds invoicing & fulfillment (no Delivery Note, no Sales Invoice, no GL posting).
    4. Automatically emails customer explaining CHASHM-002 is unavailable and recommending CHASHM-001 and CHASHM!
    """
    import asyncio
    from erp.events.email_gateway import mailbox
    from erp.orchestration.orchestrator import chief_orchestrator

    slug = f"chashm-miss-{uuid.uuid4().hex[:6]}"
    email = f"sales@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Chashm Pvt Ltd",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordChashm123!",
                "full_name": "Chashm Admin",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Seed catalog with ONLY CHASHM-001 and CHASHM (CHASHM-002 does NOT exist!)
        async with async_session_factory() as session:
            wh = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-CHASHM-01",
                warehouse_name="Chashm Primary Hub",
                is_active=True,
            )
            session.add(wh)
            await session.flush()

            sensor_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM-001",
                item_name="Wall Mounted Sensor",
                standard_rate=Decimal("10.0000"),
                is_active=True,
            )
            relay_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM",
                item_name="Relay based Fan Regulator",
                standard_rate=Decimal("5.0000"),
                is_active=True,
            )
            session.add_all([sensor_item, relay_item])
            await session.flush()

            sensor_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=sensor_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("10.0000"),
            )
            relay_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=relay_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("5.0000"),
            )
            session.add_all([sensor_stock, relay_stock])
            await session.commit()

        # Customer sends the exact user email: ordering 20 pieces of CHASHM-002
        order_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "Hassaan Tahir <misterhassan58@gmail.com>",
                "recipient": "orders@chashm.internal",
                "subject": "Order for Chashm",
                "body_text": "Hi, I want to order 20 pieces of CHASHM-002. Hassaan Tahir",
            },
            headers=headers,
        )
        assert order_res.status_code == 200, order_res.text
        dag_id = order_res.json()["dag_id"]

        dag = chief_orchestrator.get_dag(dag_id)
        assert dag is not None

        # Wait for DAG execution
        for _ in range(30):
            if dag.is_finished():
                break
            await asyncio.sleep(0.3)

        assert dag.is_finished(), f"DAG {dag_id} did not finish within timeout"

        dag_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert dag_res.status_code == 200
        dag_details = dag_res.json()
        assert dag_details["status"] == "COMPLETED"

        nodes = {n["name"]: n for n in dag_details["nodes"]}

        # 1. Node 1 flags item is NOT in catalog
        extract_out = nodes["Extract Order & Buyer Entity"]["output_result"]
        assert extract_out["raw_item_query"] == "CHASHM-002"
        assert extract_out["item_found_in_catalog"] is False
        assert extract_out["catalog_match_status"] == "NOT_IN_CATALOG"

        # 2. Node 2 flags fulfillment feasibility failed
        stock_out = nodes["Check Inventory & Stock Availability"]["output_result"]
        assert stock_out["is_in_stock"] is False
        assert stock_out["fulfillment_status"] == "ITEM_NOT_FOUND_IN_CATALOG"

        # 3. Node 3 does NOT create confirmed sales order
        prov_out = nodes["Auto-Provision Customer & Sales Order"]["output_result"]
        assert prov_out["status"] == "REJECTED_CATALOG_MISMATCH"
        assert prov_out["order_total"] == 0.0

        # 4. Node 4 holds fulfillment and generates NO invoice
        fin_out = nodes["Fulfill Delivery & Post Invoice to Ledger"]["output_result"]
        assert fin_out["delivery_note_number"] is None
        assert fin_out["invoice_number"] is None
        assert fin_out["fulfillment_status"] == "ITEM_NOT_IN_CATALOG_HELD"

        # 5. Node 5 sends catalog mismatch recommendation email
        disp_out = nodes["Dispatch Order Confirmation & Invoice"]["output_result"]
        assert disp_out["confirmation_dispatched"] is True
        assert disp_out["email_type"] == "CATALOG_MISMATCH_RECOMMENDATION"
        assert disp_out["stock_status"] == "ITEM_NOT_IN_CATALOG"
        assert disp_out["recipient"] == "misterhassan58@gmail.com"

        # 6. Verify Sent Mailbox contains the catalog notification with alternatives
        sent_emails = mailbox.get_sent(str(tenant_id))
        notif_email = next((m for m in sent_emails if m.recipient == "misterhassan58@gmail.com"), None)
        assert notif_email is not None
        assert "CHASHM-002" in notif_email.subject or "CHASHM-002" in notif_email.body
        assert "not currently available" in notif_email.body or "not" in notif_email.body.lower()
        # Verify recommended catalog alternatives are mentioned!
        assert "CHASHM-001" in notif_email.body
        assert "CHASHM" in notif_email.body

        # 7. Verify NO bogus invoices or fake items in DB
        async with async_session_factory() as session:
            fake_item = (
                await session.execute(
                    select(Item).where(
                        Item.tenant_id == tenant_id,
                        Item.item_code == "CHASHM-002",
                    )
                )
            ).scalar_one_or_none()
            assert fake_item is None  # Never fabricated!

            invoices = (
                await session.execute(
                    select(SalesInvoice).where(SalesInvoice.tenant_id == tenant_id)
                )
            ).scalars().all()
            assert len(invoices) == 0  # No invoice created!


@pytest.mark.asyncio
async def test_gemini_email_order_multi_item_fulfillment():
    """Verifies that when a customer emails ordering multiple products:
    e.g. 'Hi, I want to order 20 pieces of CHASHM-001 and 10 pieces of CHASHM. Hassaan Tahir'
    1. Gemini/order agent extracts both items.
    2. Checks inventory for all items.
    3. Auto-provisions Sales Order with 2 SalesOrderItems totaling $250.00.
    4. Fulfills Delivery Note with 2 items and decrements stock for both items.
    5. Creates Sales Invoice with 2 line items totaling $250.00.
    6. Double-entry GL commit of $250.00 (Dr 1200-AR-CUSTOMERS, Cr 4000-SALES-REVENUE).
    7. Dispatches PDF invoice and confirmation detailing both products.
    """
    import asyncio
    from erp.events.email_gateway import mailbox
    from erp.orchestration.orchestrator import chief_orchestrator
    from erp.db.models.sales import DeliveryNoteItem, SalesInvoiceItem, SalesOrderItem

    slug = f"chashm-multi-{uuid.uuid4().hex[:6]}"
    email = f"sales@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Chashm Multi Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordChashm123!",
                "full_name": "Chashm Admin",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Seed catalog with both CHASHM-001 ($10) and CHASHM ($5) with 500 stock each
        async with async_session_factory() as session:
            wh = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-CHASHM-01",
                warehouse_name="Chashm Primary Hub",
                is_active=True,
            )
            session.add(wh)
            await session.flush()

            sensor_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM-001",
                item_name="Wall Mounted Sensor",
                standard_rate=Decimal("10.0000"),
                is_active=True,
            )
            relay_item = Item(
                tenant_id=tenant_id,
                item_code="CHASHM",
                item_name="Relay based Fan Regulator",
                standard_rate=Decimal("5.0000"),
                is_active=True,
            )
            session.add_all([sensor_item, relay_item])
            await session.flush()

            sensor_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=sensor_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("10.0000"),
            )
            relay_stock = StockLevel(
                tenant_id=tenant_id,
                item_id=relay_item.item_id,
                warehouse_id=wh.warehouse_id,
                current_qty=Decimal("500.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("500.0000"),
                valuation_rate=Decimal("5.0000"),
            )
            session.add_all([sensor_stock, relay_stock])
            await session.commit()

        # Customer sends the exact multi-item order email
        order_res = await client.post(
            "/api/v1/webhooks/email/inbound",
            json={
                "sender": "Hassaan Tahir <misterhassan58@gmail.com>",
                "recipient": "orders@chashm.internal",
                "subject": "Order for Chashm Multi",
                "body_text": "Hi, I want to order 20 pieces of CHASHM-001 and 10 pieces of CHASHM. Hassaan Tahir",
            },
            headers=headers,
        )
        assert order_res.status_code == 200, order_res.text
        dag_id = order_res.json()["dag_id"]

        dag = chief_orchestrator.get_dag(dag_id)
        assert dag is not None

        # Wait for DAG execution
        for _ in range(30):
            if dag.is_finished():
                break
            await asyncio.sleep(0.3)

        assert dag.is_finished(), f"DAG {dag_id} did not finish within timeout"

        dag_res = await client.get(f"/api/v1/agents/dags/{dag_id}", headers=headers)
        assert dag_res.status_code == 200
        dag_details = dag_res.json()
        assert dag_details["status"] == "COMPLETED"

        nodes = {n["name"]: n for n in dag_details["nodes"]}

        # 1. Verify Node 1 extracted both items
        extract_out = nodes["Extract Order & Buyer Entity"]["output_result"]
        assert extract_out["is_order"] is True
        assert extract_out["item_found_in_catalog"] is True
        assert len(extract_out["items"]) == 2
        skus = {it["sku"]: it for it in extract_out["items"]}
        assert "CHASHM-001" in skus
        assert "CHASHM" in skus
        assert skus["CHASHM-001"]["quantity"] == 20.0
        assert skus["CHASHM"]["quantity"] == 10.0
        assert extract_out["order_total"] == 250.0  # 20 * 10 + 10 * 5

        # 2. Verify Node 2 verified stock for both items
        stock_out = nodes["Check Inventory & Stock Availability"]["output_result"]
        assert stock_out["is_in_stock"] is True
        assert stock_out["fulfillment_status"] == "STOCK_AVAILABLE_READY_TO_FULFILL"
        assert len(stock_out["items"]) == 2
        for it in stock_out["items"]:
            assert it["is_in_stock"] is True
            assert it["available_qty"] >= it["quantity"]

        # 3. Verify Node 3 created Sales Order for $250.00
        prov_out = nodes["Auto-Provision Customer & Sales Order"]["output_result"]
        assert prov_out["status"] == "CONFIRMED"
        assert prov_out["order_total"] == 250.0
        assert len(prov_out["items"]) == 2

        # 4. Verify Node 4 fulfilled and invoiced $250.00
        fin_out = nodes["Fulfill Delivery & Post Invoice to Ledger"]["output_result"]
        assert fin_out["invoice_number"] is not None
        assert fin_out["delivery_note_number"] is not None
        assert fin_out["invoice_amount"] == 250.0
        assert fin_out["gl_posted"] is True

        # 5. Verify Node 5 dispatched email with invoice
        disp_out = nodes["Dispatch Order Confirmation & Invoice"]["output_result"]
        assert disp_out["confirmation_dispatched"] is True
        assert disp_out["email_type"] == "SALES_INVOICE_DISPATCH"
        assert disp_out["invoice_amount"] == 250.0
        assert disp_out["recipient"] == "misterhassan58@gmail.com"

        # 6. Verify Database State
        async with async_session_factory() as session:
            # Sales Order and Items
            so = (
                await session.execute(
                    select(SalesOrder).where(
                        SalesOrder.tenant_id == tenant_id,
                        SalesOrder.order_number == prov_out["order_number"],
                    )
                )
            ).scalar_one_or_none()
            assert so is not None
            assert so.total_amount == Decimal("250.0000")

            so_items = (
                await session.execute(
                    select(SalesOrderItem).where(
                        SalesOrderItem.tenant_id == tenant_id,
                        SalesOrderItem.order_id == so.order_id,
                    )
                )
            ).scalars().all()
            assert len(so_items) == 2

            # Delivery Note and Items
            dn = (
                await session.execute(
                    select(DeliveryNote).where(
                        DeliveryNote.tenant_id == tenant_id,
                        DeliveryNote.delivery_note_number == fin_out["delivery_note_number"],
                    )
                )
            ).scalar_one_or_none()
            assert dn is not None

            dn_items = (
                await session.execute(
                    select(DeliveryNoteItem).where(
                        DeliveryNoteItem.tenant_id == tenant_id,
                        DeliveryNoteItem.delivery_note_id == dn.delivery_note_id,
                    )
                )
            ).scalars().all()
            assert len(dn_items) == 2

            # Sales Invoice and Items
            inv = (
                await session.execute(
                    select(SalesInvoice).where(
                        SalesInvoice.tenant_id == tenant_id,
                        SalesInvoice.invoice_number == fin_out["invoice_number"],
                    )
                )
            ).scalar_one_or_none()
            assert inv is not None
            assert inv.total_amount == Decimal("250.0000")

            inv_items = (
                await session.execute(
                    select(SalesInvoiceItem).where(
                        SalesInvoiceItem.tenant_id == tenant_id,
                        SalesInvoiceItem.invoice_id == inv.invoice_id,
                    )
                )
            ).scalars().all()
            assert len(inv_items) == 2

            # GL entries are exactly $250.00
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == inv.invoice_id,
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2
            ar_line = next(l for l in gle_lines if l.account_code == "1200-AR-CUSTOMERS")
            rev_line = next(l for l in gle_lines if l.account_code == "4000-SALES-REVENUE")
            assert ar_line.debit_amount == Decimal("250.0000")
            assert rev_line.credit_amount == Decimal("250.0000")

            # Stock deductions: CHASHM-001 (500 - 20 = 480), CHASHM (500 - 10 = 490)
            stock_sensor = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == sensor_item.item_id,
                    )
                )
            ).scalar_one()
            assert stock_sensor.current_qty == Decimal("480.0000")

            stock_relay = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == relay_item.item_id,
                    )
                )
            ).scalar_one()
            assert stock_relay.current_qty == Decimal("490.0000")


@pytest.mark.asyncio
async def test_gemini_order_agent_model_fallback_on_404():
    """Verifies that if a model (such as deprecated gemini-2.0-flash) returns 404,
    _call_gemini automatically falls back to subsequent candidate models (gemini-3.6-flash, etc.).
    """
    import os
    from unittest.mock import AsyncMock, patch
    from erp.commercial.gemini_order_agent import gemini_order_analyzer

    mock_catalog = [
        {
            "item_id": str(uuid.uuid4()),
            "item_code": "CHASHM-001",
            "item_name": "Wall Mounted Sensor",
            "standard_rate": 10.0,
            "available_qty": 500.0,
            "stock_uom": "Nos",
        }
    ]

    attempted_models = []

    async def mock_post(url, json=None, **kwargs):
        resp = AsyncMock()
        for m in ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash", "custom-deprecated-model"]:
            if f"models/{m}:" in url:
                attempted_models.append(m)
                if m == "custom-deprecated-model":
                    resp.is_success = False
                    resp.status_code = 404
                    resp.text = '{"error": {"code": 404, "message": "Model not available"}}'
                    return resp
                else:
                    resp.is_success = True
                    resp.status_code = 200
                    resp.json = lambda: {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json_dumps({
                                                "is_order": True,
                                                "intent": "ORDER",
                                                "confidence": 0.99,
                                                "customer_name": "Hassaan Tahir",
                                                "customer_email": "misterhassan58@gmail.com",
                                                "po_reference": "PO-123",
                                                "items": [
                                                    {
                                                        "raw_item_query": "CHASHM-001",
                                                        "requested_qty": 20.0,
                                                        "matched_item_code": "CHASHM-001",
                                                        "matched_item_name": "Wall Mounted Sensor",
                                                        "catalog_status": "EXACT_MATCH",
                                                        "unit_price": 10.0,
                                                        "line_total": 200.0,
                                                        "available_stock": 500.0,
                                                        "is_in_stock": True,
                                                    }
                                                ],
                                                "can_fulfill": True,
                                                "fulfillment_action": "FULFILL_AND_INVOICE",
                                                "total_price": 200.0,
                                                "explanation": "Valid order.",
                                                "recommended_alternatives": [],
                                                "draft_email_response": "Order confirmed.",
                                            })
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                    return resp
        resp.is_success = False
        resp.status_code = 500
        return resp

    from json import dumps as json_dumps

    with patch.dict(os.environ, {"GEMINI_MODEL": "custom-deprecated-model"}), \
         patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await gemini_order_analyzer._call_gemini(
            catalog=mock_catalog,
            sender="Hassaan Tahir <misterhassan58@gmail.com>",
            subject="Order",
            body_text="20 pieces of CHASHM-001",
            api_key="fake-test-key",
        )

        assert res is not None
        assert res.is_order is True
        assert res.total_price == 200.0
        assert attempted_models[0] == "custom-deprecated-model"
        assert attempted_models[1] == "gemini-3.6-flash"



