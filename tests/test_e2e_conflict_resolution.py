"""End-to-End Test Suite for Multi-Agent Conflict Resolution Protocol.

Verifies:
1. Competing Agent Action Collision (Quality Safety Controller vs Revenue VIP Dispatcher)
2. Mathematical Priority Hierarchy (STATUTORY_LEGAL > CONTRACTUAL_SLA)
3. True Database Lot Quarantine Hold (Blocks Order Fulfillment from Faulted Lot)
4. Revenue Agent Automated Fallback 1: Alternative Warehouse Stock Allocation & Reroute
5. Revenue Agent Automated Fallback 2: Customer Delay Notification Generation when no backup stock exists
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
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.sales import Customer, SalesOrder, SalesOrderItem


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_multi_agent_conflict_resolution_and_fallbacks():
    slug = f"arb-{uuid.uuid4().hex[:6]}"
    email = f"arb-lead@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 0: Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Autonomous Drone Propulsion Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordARB123!",
                "full_name": "Autonomous Arbiter",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Provision Warehouses, Customer, and Items in DB
        async with async_session_factory() as session:
            # Primary Warehouse (already provisioned by blueprint)
            wh1 = (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.tenant_id == tenant_id,
                        Warehouse.is_active.is_(True),
                    )
                )
            ).scalars().first()
            wh1_id = wh1.warehouse_id

            # Secondary Backup Warehouse
            wh2 = Warehouse(
                tenant_id=tenant_id,
                warehouse_code="WH-BACKUP-02",
                warehouse_name="Secondary Regional Hub",
                is_active=True,
            )
            session.add(wh2)

            # VIP Customer
            cust = Customer(
                tenant_id=tenant_id,
                customer_code=f"CUST-VIP-{uuid.uuid4().hex[:4]}",
                customer_name="Boeing Defense Systems",
                email="vip-orders@boeing.com",
                credit_limit=Decimal("500000.0000"),
            )
            session.add(cust)

            # Item 1: High-Performance Drone Motor (with backup stock in WH2)
            item1 = Item(
                tenant_id=tenant_id,
                item_code="FG-DRONE-MOTOR-X1",
                item_name="Brushless Drone Motor X1",
                standard_rate=Decimal("1000.0000"),
                is_active=True,
            )
            session.add(item1)

            # Item 2: Custom Propeller (with NO backup stock)
            item2 = Item(
                tenant_id=tenant_id,
                item_code="FG-CARBON-PROP-24",
                item_name="Carbon Fiber Propeller 24-Inch",
                standard_rate=Decimal("300.0000"),
                is_active=True,
            )
            session.add(item2)
            await session.flush()

            wh2_id = wh2.warehouse_id
            cust_id = cust.customer_id
            item1_id = item1.item_id
            item2_id = item2.item_id

            # Stock in WH1 for Item 1 (Lot 909: 50 units)
            stk_wh1_item1 = StockLevel(
                tenant_id=tenant_id,
                item_id=item1_id,
                warehouse_id=wh1_id,
                current_qty=Decimal("50.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("50.0000"),
                valuation_rate=Decimal("1000.0000"),
                lot_number="LOT-909-DEFECTIVE",
                is_quarantined=False,
            )
            # Backup Stock in WH2 for Item 1 (Lot 910: 100 units clean)
            stk_wh2_item1 = StockLevel(
                tenant_id=tenant_id,
                item_id=item1_id,
                warehouse_id=wh2_id,
                current_qty=Decimal("100.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("100.0000"),
                valuation_rate=Decimal("1000.0000"),
                lot_number="LOT-910-CLEAN",
                is_quarantined=False,
            )

            # Stock in WH1 for Item 2 (Lot 808: 20 units - NO backup in WH2)
            stk_wh1_item2 = StockLevel(
                tenant_id=tenant_id,
                item_id=item2_id,
                warehouse_id=wh1_id,
                current_qty=Decimal("20.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("20.0000"),
                valuation_rate=Decimal("300.0000"),
                lot_number="LOT-808-DEFECTIVE",
                is_quarantined=False,
            )
            session.add_all([stk_wh1_item1, stk_wh2_item1, stk_wh1_item2])

            # Sales Order 1 for VIP Customer
            so1 = SalesOrder(
                tenant_id=tenant_id,
                order_number=f"SO-VIP-{uuid.uuid4().hex[:6].upper()}",
                customer_id=cust_id,
                order_date=date.today(),
                delivery_date=date.today(),
                status="CONFIRMED",
                total_amount=Decimal("50000.0000"),
            )
            session.add(so1)
            await session.flush()
            so1_id = so1.order_id

            so1_item = SalesOrderItem(
                tenant_id=tenant_id,
                order_id=so1_id,
                item_id=item1_id,
                quantity=Decimal("50.0000"),
                unit_price=Decimal("1000.0000"),
                line_total=Decimal("50000.0000"),
            )
            session.add(so1_item)

            # Sales Order 2 for Item 2
            so2 = SalesOrder(
                tenant_id=tenant_id,
                order_number=f"SO-VIP2-{uuid.uuid4().hex[:6].upper()}",
                customer_id=cust_id,
                order_date=date.today(),
                delivery_date=date.today(),
                status="CONFIRMED",
                total_amount=Decimal("6000.0000"),
            )
            session.add(so2)
            await session.flush()
            so2_id = so2.order_id


            so2_item = SalesOrderItem(
                tenant_id=tenant_id,
                order_id=so2_id,
                item_id=item2_id,
                quantity=Decimal("20.0000"),
                unit_price=Decimal("300.0000"),
                line_total=Decimal("6000.0000"),
            )
            session.add(so2_item)
            await session.commit()

        # Step 2: Part A - Conflict Arbitration with Backup Warehouse Available
        # Quality Safety Controller (STATUTORY_LEGAL) vs Revenue VIP Dispatcher (CONTRACTUAL_SLA)
        # on LOT-909-DEFECTIVE
        arb1_res = await client.post(
            "/api/v1/quality/arbitrate-conflict",
            json={
                "lot_number": "LOT-909-DEFECTIVE",
                "item_id": str(item1_id),
                "warehouse_id": str(wh1_id),
                "order_id": str(so1_id),
                "customer_id": str(cust_id),
                "order_quantity": "50.0000",
                "order_monetary_value": "50000.00",
                "defect_type": "SURFACE_CRACK",
                "defect_confidence": 0.99,
            },
            headers=headers,
        )
        assert arb1_res.status_code == 200, arb1_res.text
        report1 = arb1_res.json()

        # Invariant 1: Statutory Legal beats Contractual SLA
        assert report1["has_collision"] is True
        assert report1["winning_policy_class"] == "STATUTORY_LEGAL"
        assert report1["winning_agent_id"] == "QUALITY_SAFETY_CONTROLLER"
        assert report1["preempted_agent_id"] == "REVENUE_VIP_DISPATCHER"
        assert "STATUTORY_LEGAL > CONTRACTUAL_SLA" in report1["preemption_boundary_violation"]

        # Invariant 2: Database Quarantine is enforced
        assert report1["stock_quarantined_in_db"] is True
        async with async_session_factory() as session:
            stk_check = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.lot_number == "LOT-909-DEFECTIVE",
                    )
                )
            ).scalar_one()
            assert stk_check.is_quarantined is True, "Lot must be quarantined in database"

        # Invariant 3: Fulfill endpoint rejects delivery from quarantined stock
        blocked_fulfill = await client.post(
            f"/api/v1/commercial/orders/{so1_id}/fulfill",
            json={"warehouse_id": str(wh1_id)},
            headers=headers,
        )
        assert blocked_fulfill.status_code == 400
        assert "QUARANTINED" in blocked_fulfill.text

        # Invariant 4: Revenue Agent Fallback 1 - Rerouted to Backup Warehouse WH2
        fb1 = report1["fallback_execution"]
        assert fb1["fallback_strategy"] == "REROUTED_TO_BACKUP_WAREHOUSE"
        assert fb1["backup_warehouse_id"] == str(wh2_id)
        assert Decimal(str(fb1["allocated_quantity"])) == Decimal("50.0000")
        assert "Fulfillment successfully rerouted" in fb1["customer_notification_text"]


        # Step 3: Part B - Conflict Arbitration when NO Backup Stock Exists
        # On LOT-808-DEFECTIVE
        arb2_res = await client.post(
            "/api/v1/quality/arbitrate-conflict",
            json={
                "lot_number": "LOT-808-DEFECTIVE",
                "item_id": str(item2_id),
                "warehouse_id": str(wh1_id),
                "order_id": str(so2_id),
                "customer_id": str(cust_id),
                "order_quantity": "20.0000",
                "order_monetary_value": "6000.00",
                "defect_type": "INTERNAL_VOID",
                "defect_confidence": 0.99,
            },
            headers=headers,
        )
        assert arb2_res.status_code == 200, arb2_res.text
        report2 = arb2_res.json()

        assert report2["winning_agent_id"] == "QUALITY_SAFETY_CONTROLLER"
        assert report2["stock_quarantined_in_db"] is True

        # Invariant 5: Revenue Agent Fallback 2 - Customer Delay Notification Issued
        fb2 = report2["fallback_execution"]
        assert fb2["fallback_strategy"] == "CUSTOMER_DELAY_NOTIFICATION_ISSUED"
        assert fb2["projected_delay_days"] == 3
        assert "Shipment delayed by 3 business days" in fb2["customer_notification_text"]
        assert "mandatory statutory quality quarantine" in fb2["customer_notification_text"]
