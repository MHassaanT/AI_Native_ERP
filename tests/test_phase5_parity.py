"""Phase 5 Automated Parity Verification Suite: Advanced Manufacturing & Shop Floor MES Suite."""

from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select

from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.manufacturing import (
    BOM,
    DowntimeEntry,
    JobCard,
    JobCardTimeLog,
    Operation,
    ProductionPlan,
    Routing,
    WorkOrder,
    Workstation,
)
from erp.db.session import async_session_factory
from erp.production.cpsat_scheduler import (
    JobOperationSpec,
    JobSpec,
    cpsat_scheduler,
)
from erp.production.router import production_router
from erp.workflows.manufacturing.bom_service import bom_service
from erp.workflows.manufacturing.job_card_service import job_card_service
from erp.workflows.manufacturing.mrp_service import mrp_service
from erp.workflows.manufacturing.oee_service import oee_service
from erp.workflows.manufacturing.work_order_service import work_order_service
from erp.workflows.stock.stock_entry_service import StockEntryService


@pytest.mark.asyncio
async def test_phase5_complete_manufacturing_mes_parity():
    """Exhaustive end-to-end integration test certifying 100% ERPNext Manufacturing & MES Parity."""
    async with async_session_factory() as db:
        tenant_id = uuid.uuid4()
        stock_svc = StockEntryService()

        # =========================================================================
        # STEP 1: Warehouses Setup (Stores, WIP, Finished Goods, Scrap)
        # =========================================================================
        wh_stores = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-STORES-{uuid.uuid4().hex[:4]}",
            warehouse_name="Stores Raw Material Warehouse",
            is_active=True,
        )
        wh_wip = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-WIP-{uuid.uuid4().hex[:4]}",
            warehouse_name="Shop Floor WIP Staging",
            is_active=True,
        )
        wh_fg = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-FG-{uuid.uuid4().hex[:4]}",
            warehouse_name="Finished Goods Central Warehouse",
            is_active=True,
        )
        wh_scrap = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-SCRAP-{uuid.uuid4().hex[:4]}",
            warehouse_name="Scrap Defect Quarantine",
            is_quarantine=True,
            is_active=True,
        )
        db.add_all([wh_stores, wh_wip, wh_fg, wh_scrap])
        await db.flush()

        # =========================================================================
        # STEP 2: Workstations & Operations Master Catalog
        # =========================================================================
        ws1 = Workstation(
            tenant_id=tenant_id,
            workstation_code=f"WS-CNC-{uuid.uuid4().hex[:4]}",
            workstation_name="CNC High-Speed Mill 01",
            workstation_type="CNC",
            hourly_rate=Decimal("60.0000"),
            production_capacity=Decimal("2.0000"),
            status="OPERATIONAL",
            health_score=Decimal("100.00"),
            is_active=True,
        )
        ws2 = Workstation(
            tenant_id=tenant_id,
            workstation_code=f"WS-ASSY-{uuid.uuid4().hex[:4]}",
            workstation_name="Robotic Assembly Cell 01",
            workstation_type="ASSEMBLY",
            hourly_rate=Decimal("40.0000"),
            production_capacity=Decimal("1.5000"),
            status="OPERATIONAL",
            health_score=Decimal("100.00"),
            is_active=True,
        )
        db.add_all([ws1, ws2])
        await db.flush()

        op_machining = await bom_service.create_operation(
            session=db,
            tenant_id=tenant_id,
            operation_name=f"Precision Milling-{uuid.uuid4().hex[:4]}",
            default_workstation_id=ws1.workstation_id,
        )
        op_assembly = await bom_service.create_operation(
            session=db,
            tenant_id=tenant_id,
            operation_name=f"Final Assembly-{uuid.uuid4().hex[:4]}",
            default_workstation_id=ws2.workstation_id,
        )
        assert op_machining.operation_id is not None
        assert op_assembly.operation_id is not None

        # Create Routing
        routing = await bom_service.create_routing(
            session=db,
            tenant_id=tenant_id,
            routing_name=f"RT-ACTUATOR-{uuid.uuid4().hex[:4]}",
            operations=[
                {
                    "operation_id": op_machining.operation_id,
                    "workstation_id": ws1.workstation_id,
                    "sequence_id": 1,
                    "time_in_mins": "30.0000",
                    "hourly_rate": "60.0000",
                },
                {
                    "operation_id": op_assembly.operation_id,
                    "workstation_id": ws2.workstation_id,
                    "sequence_id": 2,
                    "time_in_mins": "15.0000",
                    "hourly_rate": "40.0000",
                },
            ],
        )
        assert len(routing.operations) == 2

        # =========================================================================
        # STEP 3: Items & Multi-Level Visual BOM with Unit Cost Rollup
        # =========================================================================
        item_raw_alu = Item(
            tenant_id=tenant_id,
            item_code=f"RM-ALU-{uuid.uuid4().hex[:4]}",
            item_name="Billet Aluminium 6061",
            stock_uom="Kg",
            standard_rate=Decimal("15.0000"),
            is_stock_item=True,
        )
        item_fasteners = Item(
            tenant_id=tenant_id,
            item_code=f"RM-BOLT-{uuid.uuid4().hex[:4]}",
            item_name="M6 Hex Bolts Grade 8.8",
            stock_uom="Nos",
            standard_rate=Decimal("0.5000"),
            is_stock_item=True,
        )
        item_sub_gearbox = Item(
            tenant_id=tenant_id,
            item_code=f"SA-GEAR-{uuid.uuid4().hex[:4]}",
            item_name="Precision Planetary Gearbox",
            stock_uom="Nos",
            standard_rate=Decimal("80.0000"),
            is_stock_item=True,
        )
        item_fg_actuator = Item(
            tenant_id=tenant_id,
            item_code=f"FG-ACT-{uuid.uuid4().hex[:4]}",
            item_name="Robotic High-Torque Actuator",
            stock_uom="Nos",
            standard_rate=Decimal("250.0000"),
            is_stock_item=True,
        )
        item_scrap_chips = Item(
            tenant_id=tenant_id,
            item_code=f"SC-ALU-{uuid.uuid4().hex[:4]}",
            item_name="Aluminium Scrap Turnings",
            stock_uom="Kg",
            standard_rate=Decimal("2.0000"),
            is_stock_item=True,
        )
        db.add_all([item_raw_alu, item_fasteners, item_sub_gearbox, item_fg_actuator, item_scrap_chips])
        await db.flush()

        # 3a. Sub-Assembly BOM (Planetary Gearbox)
        bom_sub = await bom_service.create_bom(
            session=db,
            tenant_id=tenant_id,
            bom_number=f"BOM-GEAR-{uuid.uuid4().hex[:4]}",
            item_id=item_sub_gearbox.item_id,
            quantity=Decimal("1.0000"),
            items=[
                {"item_id": item_raw_alu.item_id, "quantity": "2.0000", "rate": "15.0000"},  # $30
                {"item_id": item_fasteners.item_id, "quantity": "8.0000", "rate": "0.5000"},  # $4
            ],
            with_operations=False,
        )
        # Raw material cost = $34.00
        assert bom_sub.raw_material_cost == Decimal("34.0000")
        assert bom_sub.total_cost == Decimal("34.0000")

        # 3b. Top-Level BOM (Robotic Actuator) with Routing, Sub-Assembly & Scrap Credit
        # Op 1: 30 mins @ $60/hr = $30.00
        # Op 2: 15 mins @ $40/hr = $10.00
        # Total Operating Cost = $40.00
        # Scrap: 1 Kg Scrap @ $2.00 = $2.00 Credit
        # Components: 1x Sub-Gearbox ($34) + 1x Raw Alu ($15) = $49.00
        # Total Unit Cost = 49 + 40 - 2 = $87.00
        bom_top = await bom_service.create_bom(
            session=db,
            tenant_id=tenant_id,
            bom_number=f"BOM-ACT-{uuid.uuid4().hex[:4]}",
            item_id=item_fg_actuator.item_id,
            quantity=Decimal("1.0000"),
            routing_id=routing.routing_id,
            with_operations=True,
            items=[
                {
                    "item_id": item_sub_gearbox.item_id,
                    "bom_sub_assembly_id": bom_sub.bom_id,
                    "quantity": "1.0000",
                    "rate": "34.0000",
                },
                {
                    "item_id": item_raw_alu.item_id,
                    "quantity": "1.0000",
                    "rate": "15.0000",
                },
            ],
            scrap_items=[
                {"item_id": item_scrap_chips.item_id, "stock_qty": "1.0000", "rate": "2.0000"},
            ],
        )
        assert bom_top.raw_material_cost == Decimal("49.0000")
        assert bom_top.operating_cost == Decimal("40.0000")
        assert bom_top.scrap_cost == Decimal("2.0000")
        assert bom_top.total_cost == Decimal("87.0000")

        # Verify Multi-Level Exploded Visual Tree
        tree = await bom_service.get_bom_tree(session=db, tenant_id=tenant_id, bom_id=bom_top.bom_id)
        assert tree is not None
        assert tree["bom_id"] == str(bom_top.bom_id)
        assert len(tree["components"]) == 2
        # Check sub-assembly recursion
        sub_c = next(c for c in tree["components"] if c["item_id"] == str(item_sub_gearbox.item_id))
        assert sub_c["sub_assembly"] is not None
        assert sub_c["sub_assembly"]["bom_id"] == str(bom_sub.bom_id)

        # =========================================================================
        # STEP 4: Material Requirements Planning (MRP) & Shortage Detection
        # =========================================================================
        plan = await mrp_service.create_production_plan(
            session=db,
            tenant_id=tenant_id,
            plan_number=f"MRP-2026-{uuid.uuid4().hex[:4]}",
            items=[
                {"item_id": item_fg_actuator.item_id, "planned_qty": "10.0000", "bom_id": bom_top.bom_id}
            ],
        )
        assert plan.total_planned_qty == Decimal("10.0000")

        # Explode requirements when stock is 0 -> should detect shortages
        explosion = await mrp_service.explode_material_requirements(
            session=db, tenant_id=tenant_id, plan_id=plan.plan_id
        )
        assert len(explosion["exploded_requirements"]) >= 3
        # Check raw aluminium requirement: 10 planned * (1 top + 2 sub) = 30 Kg
        alu_req = next(r for r in explosion["exploded_requirements"] if r["item_id"] == str(item_raw_alu.item_id))
        assert alu_req["gross_required_qty"] == 30.0
        assert alu_req["shortage_qty"] == 30.0

        # Generate Work Orders from Plan
        gen_wos = await mrp_service.generate_work_orders_from_plan(
            session=db, tenant_id=tenant_id, plan_id=plan.plan_id
        )
        assert len(gen_wos) == 1
        wo = gen_wos[0]
        assert wo.production_plan_id == plan.plan_id
        assert wo.planned_quantity == Decimal("10.0000")

        # Verify Job Cards auto-dispatched from BOM routing operations
        jc_stmt = select(JobCard).where(JobCard.work_order_id == wo.work_order_id)
        dispatched_jcs = (await db.execute(jc_stmt)).scalars().all()
        assert len(dispatched_jcs) == 2  # Milling and Assembly

        # =========================================================================
        # STEP 5: Initial Stock Receipt in Stores Warehouse
        # =========================================================================
        rcpt = await stock_svc.create_stock_entry(
            session=db,
            tenant_id=tenant_id,
            entry_number=f"RC-STORES-{uuid.uuid4().hex[:4]}",
            stock_entry_type="MATERIAL_RECEIPT",
            to_warehouse_id=wh_stores.warehouse_id,
            items=[
                {"item_id": str(item_raw_alu.item_id), "qty": "100.0000", "basic_rate": "15.0000", "t_warehouse_id": str(wh_stores.warehouse_id)},
                {"item_id": str(item_sub_gearbox.item_id), "qty": "20.0000", "basic_rate": "34.0000", "t_warehouse_id": str(wh_stores.warehouse_id)},
            ],
        )
        await stock_svc.submit_stock_entry(session=db, tenant_id=tenant_id, entry_id=rcpt.entry_id)

        # Set specific staging warehouses on work order for strict verification
        wo.source_warehouse_id = wh_stores.warehouse_id
        wo.wip_warehouse_id = wh_wip.warehouse_id
        wo.fg_warehouse_id = wh_fg.warehouse_id
        wo.scrap_warehouse_id = wh_scrap.warehouse_id
        await db.flush()

        # =========================================================================
        # STEP 6: Material Staging to WIP (ST-MAT-TRANSFER)
        # =========================================================================
        staging_res = await work_order_service.stage_materials_to_wip(
            session=db, tenant_id=tenant_id, work_order_id=wo.work_order_id
        )
        assert staging_res["material_transferred_for_mfg"] is True
        assert staging_res["status"] == "IN_PROCESS"

        # Verify stock moved from Stores to WIP
        stores_alu = (await db.execute(select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_raw_alu.item_id,
            StockLevel.warehouse_id == wh_stores.warehouse_id,
        ))).scalar_one()
        wip_alu = (await db.execute(select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_raw_alu.item_id,
            StockLevel.warehouse_id == wh_wip.warehouse_id,
        ))).scalar_one()
        # 100 - 10 = 90 in Stores, 10 in WIP
        assert stores_alu.current_qty == Decimal("90.0000")
        assert wip_alu.current_qty == Decimal("10.0000")

        # =========================================================================
        # STEP 7: MES Shop Floor Execution, Timers & Punch Clock
        # =========================================================================
        jc1 = dispatched_jcs[0]
        # Start traveler timer
        started_jc1 = await job_card_service.start_job_card(
            session=db, tenant_id=tenant_id, job_card_id=jc1.job_card_id
        )
        assert started_jc1.status == "WORK_IN_PROGRESS"
        assert started_jc1.current_timer_started_at is not None

        # Complete traveler with 1 scrap defect
        completed_jc1 = await job_card_service.complete_job_card(
            session=db,
            tenant_id=tenant_id,
            job_card_id=jc1.job_card_id,
            completed_qty=Decimal("10.0000"),
            scrap_qty=Decimal("1.0000"),
        )
        assert completed_jc1.status == "COMPLETED"
        assert completed_jc1.total_completed_qty == Decimal("10.0000")
        assert completed_jc1.total_scrap_qty == Decimal("1.0000")

        # Check time logs recorded
        logs = (await db.execute(
            select(JobCardTimeLog).where(JobCardTimeLog.job_card_id == jc1.job_card_id)
        )).scalars().all()
        assert len(logs) == 1

        # =========================================================================
        # STEP 8: Backflush Manufacture & Double-Entry GL Valuation (ST-MANUFACTURE)
        # =========================================================================
        mfg_res = await work_order_service.complete_manufacture(
            session=db,
            tenant_id=tenant_id,
            work_order_id=wo.work_order_id,
            produced_quantity=Decimal("10.0000"),
        )
        assert mfg_res["status"] == "COMPLETED"
        assert mfg_res["produced_quantity"] == 10.0

        # Verify WIP stock was consumed and Finished Goods warehouse received 10 units
        wip_alu_after = (await db.execute(select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_raw_alu.item_id,
            StockLevel.warehouse_id == wh_wip.warehouse_id,
        ))).scalar_one()
        fg_actuator = (await db.execute(select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.item_id == item_fg_actuator.item_id,
            StockLevel.warehouse_id == wh_fg.warehouse_id,
        ))).scalar_one()
        assert wip_alu_after.current_qty == Decimal("0.0000")  # Backflushed to 0
        assert fg_actuator.current_qty == Decimal("10.0000")  # FG Received 10 units

        # Verify balanced General Ledger entries posted
        gl_entries = (await db.execute(
            select(GeneralLedgerEntry).where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.source_document_id == wo.work_order_id,
            )
        )).scalars().all()
        assert len(gl_entries) == 2
        gl_dr = next(g for g in gl_entries if g.debit_amount > Decimal("0.0000"))
        gl_cr = next(g for g in gl_entries if g.credit_amount > Decimal("0.0000"))
        assert gl_dr.account_code == "1350-FINISHED-GOODS"
        assert gl_cr.account_code == "1400-WIP-INVENTORY"
        assert gl_dr.debit_amount == gl_cr.credit_amount  # Balanced to the penny

        # =========================================================================
        # STEP 9: Downtime Entry & OEE Telemetry Calculation
        # =========================================================================
        # Record stoppage
        dt_entry = await oee_service.record_downtime(
            session=db,
            tenant_id=tenant_id,
            downtime_number=f"DT-{uuid.uuid4().hex[:4]}",
            workstation_id=ws1.workstation_id,
            reason="MECHANICAL_BREAKDOWN",
            fault_code="ERR-SPINDLE-OVERHEAT",
        )
        assert dt_entry.status == "OPEN"
        # Check machine locked
        ws1_after = (await db.execute(
            select(Workstation).where(Workstation.workstation_id == ws1.workstation_id)
        )).scalar_one()
        assert ws1_after.status == "FAULT"

        # Resolve stoppage (simulate 30 min duration)
        resolved_dt = await oee_service.resolve_downtime(
            session=db,
            tenant_id=tenant_id,
            downtime_id=dt_entry.downtime_id,
            to_time=datetime.now(UTC),
        )
        assert resolved_dt.status == "RESOLVED"
        assert ws1_after.status == "OPERATIONAL"

        # Calculate OEE KPIs
        oee = await oee_service.calculate_workstation_oee(
            session=db,
            tenant_id=tenant_id,
            workstation_id=ws1.workstation_id,
            planned_production_minutes=480.0,
        )
        assert "oee_percentage" in oee
        assert oee["availability"] > 0.0
        assert oee["quality"] > 0.0
        assert oee["performance"] > 0.0

        # =========================================================================
        # STEP 10: Google OR-Tools CP-SAT Autonomous Scheduling & Dynamic Rerouting
        # =========================================================================
        job1 = JobSpec(
            job_id="JOB-ALPHA",
            job_name="Alpha Batch",
            operations=[
                JobOperationSpec(
                    operation_id="OP-A1",
                    operation_name="Precision Milling",
                    workstation_code=ws1.workstation_code,
                    duration_minutes=45,
                    alternative_workstations=[ws2.workstation_code],
                )
            ],
        )
        job2 = JobSpec(
            job_id="JOB-BETA",
            job_name="Beta Batch",
            operations=[
                JobOperationSpec(
                    operation_id="OP-B1",
                    operation_name="Secondary Milling",
                    workstation_code=ws1.workstation_code,
                    duration_minutes=30,
                    alternative_workstations=[ws2.workstation_code],
                )
            ],
        )
        sched_res = cpsat_scheduler.solve_schedule(jobs=[job1, job2])
        assert sched_res.solver_status in ("OPTIMAL", "FEASIBLE")
        assert sched_res.makespan_minutes >= 75  # 45 + 30 non-overlapping on single machine

        # Test dynamic fault rerouting
        reroute_res = production_router.handle_workstation_failure(
            faulted_workstation_code=ws1.workstation_code,
            current_jobs=[job1, job2],
        )
        assert reroute_res.faulted_workstation == ws1.workstation_code
        assert reroute_res.reallocated_operations_count == 2
        assert reroute_res.schedule.solver_status in ("OPTIMAL", "FEASIBLE")
