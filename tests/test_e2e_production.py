"""End-to-End Test Suite for Production & Shop-Floor Lifecycle.

Verifies:
1. Work Order Creation & BOM Raw Material Reservation
2. Global CP-SAT Scheduling Solution
3. Edge IoT Catastrophic Fault Ingestion & Automatic Machine Lockout / Dynamic Rerouting
4. Work Order Completion, Raw Material Deduction, Finished Good SLE & GL Valuation Transfer
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
from erp.db.models.manufacturing import BOM, BOMItem, MaintenanceTicket, WorkOrder, Workstation


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_production_and_shop_floor_full_lifecycle():
    slug = f"mfg-{uuid.uuid4().hex[:6]}"
    email = f"plant-manager@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 0: Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Precision Turbine Manufacturing Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordMFG123!",
                "full_name": "Plant Manager",
                "auto_provision": True,
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create Workstations
        ws1_res = await client.post(
            "/api/v1/production/workstations",
            json={
                "workstation_code": "WS-CNC-01",
                "workstation_name": "5-Axis High-Precision CNC Mill 01",
                "hourly_rate": "85.0000",
                "status": "OPERATIONAL",
            },
            headers=headers,
        )
        assert ws1_res.status_code == 201, ws1_res.text
        ws1_id = uuid.UUID(ws1_res.json()["workstation_id"])

        ws2_res = await client.post(
            "/api/v1/production/workstations",
            json={
                "workstation_code": "WS-CNC-02",
                "workstation_name": "5-Axis Backup CNC Mill 02",
                "hourly_rate": "85.0000",
                "status": "OPERATIONAL",
            },
            headers=headers,
        )
        assert ws2_res.status_code == 201, ws2_res.text
        ws2_id = uuid.UUID(ws2_res.json()["workstation_id"])

        # Setup Items, BOM, and Inventory Stock in DB
        async with async_session_factory() as session:
            wh = (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.tenant_id == tenant_id,
                        Warehouse.is_active.is_(True),
                    )
                )
            ).scalars().first()
            assert wh is not None
            wh_id = wh.warehouse_id

            # Raw Material 1: Ingot
            item_ingot = Item(
                tenant_id=tenant_id,
                item_code="RAW-INGOT-TI",
                item_name="Titanium Alloy Ingot Grade 5",
                standard_rate=Decimal("400.0000"),
                is_active=True,
            )
            session.add(item_ingot)

            # Raw Material 2: Fastener Ring
            item_ring = Item(
                tenant_id=tenant_id,
                item_code="RAW-RING-SEAL",
                item_name="High-Temp Inconel Seal Ring",
                standard_rate=Decimal("50.0000"),
                is_active=True,
            )
            session.add(item_ring)

            # Finished Good: Turbine Housing
            item_fg = Item(
                tenant_id=tenant_id,
                item_code="FG-TURBINE-HOUSING",
                item_name="Aero Turbine Housing Subassembly",
                standard_rate=Decimal("1500.0000"),
                is_active=True,
            )
            session.add(item_fg)
            await session.flush()

            # Bill of Materials: 1 Housing requires 2 Ingots ($800) + 4 Rings ($200) = $1,000 Material Cost
            bom = BOM(
                tenant_id=tenant_id,
                bom_number=f"BOM-HOUSING-{uuid.uuid4().hex[:4].upper()}",
                item_id=item_fg.item_id,
                quantity=Decimal("1.0000"),
                total_cost=Decimal("1000.0000"),
                is_active=True,
            )
            session.add(bom)
            await session.flush()

            bom_item1 = BOMItem(
                tenant_id=tenant_id,
                bom_id=bom.bom_id,
                item_id=item_ingot.item_id,
                quantity=Decimal("2.0000"),
                rate=Decimal("400.0000"),
                amount=Decimal("800.0000"),
            )
            bom_item2 = BOMItem(
                tenant_id=tenant_id,
                bom_id=bom.bom_id,
                item_id=item_ring.item_id,
                quantity=Decimal("4.0000"),
                rate=Decimal("50.0000"),
                amount=Decimal("200.0000"),
            )
            session.add_all([bom_item1, bom_item2])

            # Initial stock: 100 Ingots, 200 Rings, 0 FG
            stk_ingot = StockLevel(
                tenant_id=tenant_id,
                item_id=item_ingot.item_id,
                warehouse_id=wh_id,
                current_qty=Decimal("100.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("100.0000"),
                valuation_rate=Decimal("400.0000"),
            )
            stk_ring = StockLevel(
                tenant_id=tenant_id,
                item_id=item_ring.item_id,
                warehouse_id=wh_id,
                current_qty=Decimal("200.0000"),
                reserved_qty=Decimal("0.0000"),
                available_qty=Decimal("200.0000"),
                valuation_rate=Decimal("50.0000"),
            )
            session.add_all([stk_ingot, stk_ring])
            await session.commit()

            fg_id = item_fg.item_id
            ingot_id = item_ingot.item_id
            ring_id = item_ring.item_id
            bom_id = bom.bom_id

        # Step 2: Create Work Order (10 units FG) -> Reserves 20 Ingots & 40 Rings
        wo_num = f"WO-{uuid.uuid4().hex[:6].upper()}"
        wo_res = await client.post(
            "/api/v1/production/work-orders",
            json={
                "work_order_number": wo_num,
                "item_id": str(fg_id),
                "bom_id": str(bom_id),
                "workstation_id": str(ws1_id),
                "warehouse_id": str(wh_id),
                "planned_quantity": "10.0000",
            },
            headers=headers,
        )
        assert wo_res.status_code == 201, wo_res.text
        wo_data = wo_res.json()
        wo_id = uuid.UUID(wo_data["work_order_id"])
        assert wo_data["status"] == "SCHEDULED"

        # Verify DB: Component stock levels have reserved_qty incremented
        async with async_session_factory() as session:
            ingot_stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == ingot_id,
                    )
                )
            ).scalar_one()
            assert ingot_stk.reserved_qty == Decimal("20.0000")
            assert ingot_stk.available_qty == Decimal("80.0000")

            ring_stk = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == ring_id,
                    )
                )
            ).scalar_one()
            assert ring_stk.reserved_qty == Decimal("40.0000")
            assert ring_stk.available_qty == Decimal("160.0000")

        # Step 3: Solve Job Schedule with CP-SAT
        sched_res = await client.post(
            "/api/v1/production/solve-schedule",
            json={"jobs": []},
            headers=headers,
        )
        assert sched_res.status_code == 200, sched_res.text
        sched_data = sched_res.json()
        assert sched_data["solver_status"] in ["OPTIMAL", "FEASIBLE"]
        assert sched_data["makespan_minutes"] > 0


        # Step 4: Ingest Catastrophic IoT Telemetry Frame for WS-CNC-01
        # High vibration and high temperature triggering emergency lockout and automatic reroute
        telemetry_res = await client.post(
            "/api/v1/iot/telemetry",
            json={
                "workstation_code": "WS-CNC-01",
                "vibration_rms_mm_s": 8.5,
                "bearing_temp_c": 98.0,
                "motor_power_kw": 22.0,
                "rotational_speed_rpm": 3200.0,
                "acoustic_emissions_db": 92.0,
            },
            headers=headers,
        )
        assert telemetry_res.status_code == 200, telemetry_res.text
        action_plan = telemetry_res.json()
        assert action_plan["emergency_lockout"] is True
        assert action_plan["work_order_created"] is True
        assert action_plan["rerouted"] is True

        # Verify DB: Workstation marked as CRITICAL_FAULT and Maintenance Ticket created
        async with async_session_factory() as session:
            ws1 = (
                await session.execute(
                    select(Workstation).where(
                        Workstation.tenant_id == tenant_id,
                        Workstation.workstation_id == ws1_id,
                    )
                )
            ).scalar_one()
            assert ws1.status == "CRITICAL_FAULT"

            ticket = (
                await session.execute(
                    select(MaintenanceTicket).where(
                        MaintenanceTicket.tenant_id == tenant_id,
                        MaintenanceTicket.workstation_id == ws1_id,
                    )
                )
            ).scalars().first()
            assert ticket is not None
            assert ticket.priority == "CRITICAL"

        # Step 5: Complete Work Order
        # Raw materials consumed (20 Ingots + 40 Rings = $10,000), 10 FG produced
        complete_res = await client.post(
            f"/api/v1/production/work-orders/{wo_id}/complete",
            json={
                "produced_quantity": "10.0000",
                "warehouse_id": str(wh_id),
            },
            headers=headers,
        )
        assert complete_res.status_code == 200, complete_res.text
        comp_data = complete_res.json()
        assert comp_data["status"] == "COMPLETED"
        assert Decimal(comp_data["valuation_transferred"]) == Decimal("10000.0000")


        # Verify DB: Inventory updated & SLE written
        async with async_session_factory() as session:
            # Component stock deducted and reserved released
            stk_i = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == ingot_id,
                    )
                )
            ).scalar_one()
            assert stk_i.current_qty == Decimal("80.0000")
            assert stk_i.reserved_qty == Decimal("0.0000")

            stk_r = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == ring_id,
                    )
                )
            ).scalar_one()
            assert stk_r.current_qty == Decimal("160.0000")
            assert stk_r.reserved_qty == Decimal("0.0000")

            # Finished good stock added
            stk_fg = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == fg_id,
                    )
                )
            ).scalar_one()
            assert stk_fg.current_qty == Decimal("10.0000")
            assert stk_fg.valuation_rate == Decimal("1000.0000")

            # SLE entries verified
            sles = (
                await session.execute(
                    select(StockLedgerEntry).where(
                        StockLedgerEntry.tenant_id == tenant_id,
                        StockLedgerEntry.source_document_id == wo_id,
                    )
                )
            ).scalars().all()
            # 2 issues (ingot, ring) + 1 receipt (fg) = 3 SLEs
            assert len(sles) == 3
            types = [s.source_document_type for s in sles]
            assert types.count("WORK_ORDER_ISSUE") == 2
            assert types.count("WORK_ORDER_RECEIPT") == 1

            # GL Valuation Transfer: Dr 1350-FINISHED-GOODS / Cr 1300-RAW-MATERIALS
            gle_lines = (
                await session.execute(
                    select(GeneralLedgerEntry).where(
                        GeneralLedgerEntry.tenant_id == tenant_id,
                        GeneralLedgerEntry.source_document_id == wo_id,
                    )
                )
            ).scalars().all()
            assert len(gle_lines) == 2
            total_debit = sum(line.debit_amount for line in gle_lines)
            total_credit = sum(line.credit_amount for line in gle_lines)
            assert total_debit == Decimal("10000.0000")
            assert total_credit == Decimal("10000.0000")
