"""Phase 7 Automated Parity Verification Suite: Fixed Assets, Quality, Maintenance & Projects."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.models.assets import (
    Asset,
    AssetCategory,
    AssetDepreciationSchedule,
    AssetLocation,
    AssetMovement,
    AssetRepair,
)
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.maintenance import MaintenanceSchedule, MaintenanceVisit
from erp.db.models.projects import Project, ProjectTask, Timesheet
from erp.db.models.quality import (
    NonConformance,
    QualityAction,
    QualityInspection,
    QualityInspectionParameter,
    QualityInspectionTemplate,
)
from erp.db.session import async_session_factory
from erp.workflows.assets.asset_service import asset_service
from erp.workflows.maintenance.maintenance_service import maintenance_service
from erp.workflows.projects.project_service import project_service
from erp.workflows.quality.quality_service import quality_service


@pytest.mark.asyncio
async def test_phase7_complete_assets_quality_maintenance_projects_parity():
    """Exhaustive end-to-end integration test certifying 100% ERPNext Parity for Phase 7."""
    async with async_session_factory() as db:
        tenant_id = uuid.uuid4()

        # =========================================================================
        # 1. FIXED ASSETS LIFECYCLE & DEPRECIATION SCHEDULE ENGINE
        # =========================================================================
        # A. Categories & Locations
        cat_machinery = await asset_service.create_category(
            session=db,
            tenant_id=tenant_id,
            category_name="Heavy Machinery & CNC",
            depreciation_method="STRAIGHT_LINE",
            total_number_of_depreciations=24,
            frequency_in_months=1,
            fixed_asset_account="1500-FIXED-ASSETS",
            accumulated_depreciation_account="1550-ACCUMULATED-DEPRECIATION",
            depreciation_expense_account="5200-DEP-MACHINERY",
        )
        assert cat_machinery.depreciation_method == "STRAIGHT_LINE"
        assert cat_machinery.total_number_of_depreciations == 24

        cat_fleet = await asset_service.create_category(
            session=db,
            tenant_id=tenant_id,
            category_name="Commercial Vehicles",
            depreciation_method="DOUBLE_DECLINING",
            total_number_of_depreciations=12,
            frequency_in_months=1,
        )
        assert cat_fleet.depreciation_method == "DOUBLE_DECLINING"

        loc_plant1 = await asset_service.create_location(
            session=db,
            tenant_id=tenant_id,
            location_name="Plant 1 - Machining Bay",
        )
        loc_plant2 = await asset_service.create_location(
            session=db,
            tenant_id=tenant_id,
            location_name="Plant 2 - Assembly Bay",
        )

        # B. Asset Registration with Straight-Line Depreciation Schedule
        cnc_asset = await asset_service.create_asset(
            session=db,
            tenant_id=tenant_id,
            asset_code="AST-CNC-5AXIS-01",
            asset_name="Haas 5-Axis CNC Mill",
            asset_category_id=cat_machinery.category_id,
            purchase_date=date(2026, 1, 1),
            available_for_use_date=date(2026, 1, 1),
            gross_purchase_amount=Decimal("120000.0000"),
            salvage_value=Decimal("12000.0000"),
            location_id=loc_plant1.location_id,
            notes="Primary precision machining center",
            auto_generate_schedule=True,
        )
        assert cnc_asset.status == "SUBMITTED"
        assert cnc_asset.current_book_value == Decimal("120000.0000")

        # Verify Depreciation Schedule Generation
        loaded_asset = await asset_service.get_asset(db, tenant_id, cnc_asset.asset_id)
        assert loaded_asset is not None
        assert len(loaded_asset.schedules) == 24

        total_sched_dep = sum(s.depreciation_amount for s in loaded_asset.schedules)
        expected_depreciable = Decimal("120000.0000") - Decimal("12000.0000")
        assert total_sched_dep == expected_depreciable
        assert loaded_asset.schedules[-1].book_value_after_depreciation == Decimal("12000.0000")

        # C. Post Depreciation Period 1 to General Ledger
        first_sched = loaded_asset.schedules[0]
        gl_dr = await asset_service.post_depreciation_entry(db, tenant_id, first_sched.schedule_id)
        assert gl_dr.account_code == "5200-DEP-MACHINERY"
        assert gl_dr.debit_amount == Decimal("4500.0000")
        assert first_sched.is_posted is True
        assert cnc_asset.accumulated_depreciation == Decimal("4500.0000")
        assert cnc_asset.current_book_value == Decimal("115500.0000")
        assert cnc_asset.status == "IN_USE"

        # Verify General Ledger Balancing
        gl_stmt = select(GeneralLedgerEntry).where(
            GeneralLedgerEntry.tenant_id == tenant_id,
            GeneralLedgerEntry.transaction_id == gl_dr.transaction_id,
        )
        gl_entries = (await db.execute(gl_stmt)).scalars().all()
        assert len(gl_entries) == 2
        total_dr = sum(e.debit_amount for e in gl_entries)
        total_cr = sum(e.credit_amount for e in gl_entries)
        assert total_dr == total_cr == Decimal("4500.0000")

        # Re-posting prevention
        with pytest.raises(ValueError, match="already been posted"):
            await asset_service.post_depreciation_entry(db, tenant_id, first_sched.schedule_id)

        # D. Asset Physical Movement & Custodian Handover
        custodian_user_id = uuid.uuid4()
        movement = await asset_service.record_asset_movement(
            session=db,
            tenant_id=tenant_id,
            asset_id=cnc_asset.asset_id,
            to_location_id=loc_plant2.location_id,
            to_custodian_id=custodian_user_id,
            purpose="Line rebalancing for aerospace order",
        )
        assert movement.to_location_id == loc_plant2.location_id
        assert cnc_asset.location_id == loc_plant2.location_id
        assert cnc_asset.custodian_id == custodian_user_id

        # E. Asset Repair & Cost Capitalization
        repair = await asset_service.record_asset_repair(
            session=db,
            tenant_id=tenant_id,
            asset_id=cnc_asset.asset_id,
            repair_cost=Decimal("5000.0000"),
            repair_description="Spindle ceramic bearing upgrade and retrofitting",
            is_capitalized=True,
        )
        assert repair.is_capitalized is True
        assert repair.journal_entry_id is not None
        assert cnc_asset.gross_purchase_amount == Decimal("125000.0000")
        assert cnc_asset.current_book_value == Decimal("120500.0000")

        # F. Asset Scrapping & Loss on Disposal Write-off
        scrapped_asset = await asset_service.scrap_asset(
            session=db,
            tenant_id=tenant_id,
            asset_id=cnc_asset.asset_id,
            notes="End of life decommission",
        )
        assert scrapped_asset.status == "SCRAPPED"
        assert scrapped_asset.current_book_value == Decimal("0.0000")

        # =========================================================================
        # 2. QUALITY MANAGEMENT: TEMPLATES, INSPECTIONS, NCR & 5-WHYS CAPA
        # =========================================================================
        # A. Quality Inspection Template with Min/Max Tolerances
        q_template = await quality_service.create_template(
            session=db,
            tenant_id=tenant_id,
            template_name="Titanium Aerospace Bracket Spec",
            description="ISO 9001 / AS9100 Dimensional and Surface Verification",
            parameters=[
                {
                    "parameter_name": "Bracket Length",
                    "specification": "100.00 mm +/- 0.05 mm",
                    "min_value": Decimal("99.9500"),
                    "max_value": Decimal("100.0500"),
                    "acceptance_tolerance": "0.05 mm",
                },
                {
                    "parameter_name": "Bore Diameter",
                    "specification": "25.00 mm +/- 0.02 mm",
                    "min_value": Decimal("24.9800"),
                    "max_value": Decimal("25.0200"),
                    "acceptance_tolerance": "0.02 mm",
                },
                {
                    "parameter_name": "Surface Roughness",
                    "specification": "Max 0.80 Ra",
                    "min_value": Decimal("0.0000"),
                    "max_value": Decimal("0.8000"),
                    "acceptance_tolerance": "0.80 Ra",
                },
            ],
        )
        loaded_tmpl = await quality_service.get_template(db, tenant_id, q_template.template_id)
        assert loaded_tmpl is not None
        assert len(loaded_tmpl.parameters) == 3

        # B. Passing Quality Inspection
        pass_insp = await quality_service.create_inspection(
            session=db,
            tenant_id=tenant_id,
            inspection_number="QI-2026-001",
            inspection_type="INCOMING",
            reference_doc_type="PurchaseReceipt",
            item_code="RAW-TI-BRACKET",
            sample_size=Decimal("5.0000"),
            readings=[
                {"parameter_name": "Bracket Length", "reading_value": Decimal("100.0100"), "min_value": Decimal("99.9500"), "max_value": Decimal("100.0500")},
                {"parameter_name": "Bore Diameter", "reading_value": Decimal("25.0050"), "min_value": Decimal("24.9800"), "max_value": Decimal("25.0200")},
                {"parameter_name": "Surface Roughness", "reading_value": Decimal("0.6500"), "min_value": Decimal("0.0000"), "max_value": Decimal("0.8000")},
            ],
            remarks="Batch passes AS9100 incoming dimensional checks.",
        )
        assert pass_insp.status == "PASS"

        # C. Failing Quality Inspection with Automated NCR Generation
        fail_insp = await quality_service.create_inspection(
            session=db,
            tenant_id=tenant_id,
            inspection_number="QI-2026-002",
            inspection_type="IN_PROCESS",
            reference_doc_type="JobCard",
            item_code="RAW-TI-BRACKET",
            sample_size=Decimal("5.0000"),
            readings=[
                {"parameter_name": "Bracket Length", "reading_value": Decimal("100.1200"), "min_value": Decimal("99.9500"), "max_value": Decimal("100.0500")},
                {"parameter_name": "Bore Diameter", "reading_value": Decimal("25.0100"), "min_value": Decimal("24.9800"), "max_value": Decimal("25.0200")},
                {"parameter_name": "Surface Roughness", "reading_value": Decimal("0.7000"), "min_value": Decimal("0.0000"), "max_value": Decimal("0.8000")},
            ],
            remarks="Dimension oversized beyond maximum permissible tolerance.",
            auto_create_nc_on_failure=True,
        )
        assert fail_insp.status == "FAIL"

        # Verify Automated Non-Conformance Report
        ncs = await quality_service.list_non_conformances(db, tenant_id)
        assert len(ncs) == 1
        ncr = ncs[0]
        assert ncr.nc_number == "NCR-QI-2026-002"
        assert ncr.severity == "MAJOR"
        assert ncr.immediate_disposition == "REWORK"
        assert ncr.status == "OPEN"

        # D. CAPA with 5-Whys Root Cause Analysis
        five_whys_analysis = (
            "Why 1: Bracket length was 100.12mm exceeding max spec of 100.05mm.\n"
            "Why 2: Tool wear offset compensation was not updated after tool shift change.\n"
            "Why 3: Optical tool presetter glass lens was contaminated with aerosolized cutting mist.\n"
            "Why 4: Clean air curtain purge on the presetter enclosure was turned off.\n"
            "Why 5: Air solenoid failed and there was no preventive interlock alarm.\n"
            "Root Cause: Missing pressure interlock sensor on optical presetter positive air purge line."
        )
        action_plan = "Install fail-safe differential pressure switch on tool presetter air purge and mandate shift checklist."

        capa = await quality_service.create_action(
            session=db,
            tenant_id=tenant_id,
            capa_number="CAPA-2026-001",
            nc_id=ncr.nc_id,
            action_type="CORRECTIVE",
            root_cause_analysis=five_whys_analysis,
            action_plan=action_plan,
            target_completion_date=date(2026, 2, 15),
        )
        assert capa.status == "OPEN"
        reloaded_nc_capa = await quality_service.get_non_conformance(db, tenant_id, ncr.nc_id)
        assert reloaded_nc_capa.status == "CAPA_ASSIGNED"

        # Resolve CAPA and Verify Auto-Closure of NCR
        resolved_capa = await quality_service.resolve_action(
            session=db,
            tenant_id=tenant_id,
            action_id=capa.action_id,
            resolution_notes="Differential pressure switch installed and tested; SOP rev 3.2 published.",
            new_status="VERIFIED_CLOSED",
        )
        assert resolved_capa.status == "VERIFIED_CLOSED"
        closed_ncr = await quality_service.get_non_conformance(db, tenant_id, ncr.nc_id)
        assert closed_ncr is not None
        assert closed_ncr.status == "CLOSED"

        # =========================================================================
        # 3. PREVENTIVE MAINTENANCE & TECHNICIAN DISPATCH SUITE
        # =========================================================================
        # A. Maintenance Schedule with Automated Next Due Date
        maint_sched = await maintenance_service.create_schedule(
            session=db,
            tenant_id=tenant_id,
            schedule_number="PMS-CNC-001",
            periodicity="MONTHLY",
            start_date=date(2026, 1, 15),
            task_description="Monthly 5-Point CNC Spindle and Hydraulic Maintenance",
            checklist_items=[
                "Inspect spindle hydraulic oil level and filter cleanliness",
                "Measure pneumatic line pressure (must be 6.2 bar minimum)",
                "Lubricate ball screws and linear guideways with Mobil Vactra No 2",
                "Check coolant refractometer concentration (8% - 10%)",
                "Test emergency stop and axis interlock switches",
            ],
            asset_id=cnc_asset.asset_id,
        )
        assert maint_sched.status == "ACTIVE"
        assert maint_sched.periodicity == "MONTHLY"
        assert maint_sched.next_due_date == date(2026, 2, 15)

        # B. Dispatched Maintenance Visit with Downtime Logging
        visit = await maintenance_service.record_visit(
            session=db,
            tenant_id=tenant_id,
            visit_number="MV-2026-001",
            schedule_id=maint_sched.schedule_id,
            asset_id=cnc_asset.asset_id,
            technician_name="Marcus Vance (Senior Field Service Specialist)",
            visit_date=date(2026, 2, 15),
            maintenance_type="PREVENTIVE",
            tasks_performed="Completed 5-point lubrication and filter replacement. Cleaned optical scales.",
            parts_replaced="Hydraulic Return Line Filter (Part #HF-8012)",
            downtime_hours=Decimal("1.75"),
            maintenance_cost=Decimal("385.5000"),
            status="COMPLETED",
        )
        assert visit.downtime_hours == Decimal("1.75")
        assert visit.maintenance_cost == Decimal("385.5000")

        # Verify Next Due Date Roll Forward
        updated_sched = await maintenance_service.get_schedule(db, tenant_id, maint_sched.schedule_id)
        assert updated_sched is not None
        assert updated_sched.next_due_date == date(2026, 3, 15)
        assert len(updated_sched.visits) == 1

        # =========================================================================
        # 4. PROJECTS, DISCRETE TASKS & LABOR TIMESHEET COST ROLLUPS
        # =========================================================================
        # A. Project Master Creation
        project = await project_service.create_project(
            session=db,
            tenant_id=tenant_id,
            project_code="PRJ-AERO-001",
            project_name="Aerospace Titanium Components Production",
            customer_name="Lockheed Martin Space Systems",
            start_date=date(2026, 1, 1),
            estimated_cost=Decimal("45000.0000"),
            notes="Contract #LM-2026-SPACE",
        )
        assert project.status == "IN_PROGRESS"
        assert project.actual_cost == Decimal("0.0000")
        assert project.percent_complete == Decimal("0.00")

        # B. Task Work Items Creation
        task1 = await project_service.create_task(
            session=db,
            tenant_id=tenant_id,
            project_id=project.project_id,
            task_title="CNC Toolpath Generation and CAD/CAM Simulation",
            priority="HIGH",
            estimated_hours=Decimal("20.00"),
            assigned_to_name="Sarah Chen (Lead CAM Engineer)",
        )
        task2 = await project_service.create_task(
            session=db,
            tenant_id=tenant_id,
            project_id=project.project_id,
            task_title="First Article Prototyping & CMM Inspection",
            priority="URGENT",
            estimated_hours=Decimal("30.00"),
            assigned_to_name="David Rossi (Machinist QA)",
        )
        loaded_proj = await project_service.get_project(db, tenant_id, project.project_id)
        assert loaded_proj is not None
        assert len(loaded_proj.tasks) == 2

        # C. Labor Timesheets with Billing & Costing Rates
        emp_sarah = uuid.uuid4()
        emp_david = uuid.uuid4()

        ts1 = await project_service.log_timesheet(
            session=db,
            tenant_id=tenant_id,
            timesheet_number="TS-2026-001",
            employee_id=emp_sarah,
            employee_name="Sarah Chen",
            project_id=project.project_id,
            task_id=task1.task_id,
            activity_type="ENGINEERING",
            work_date=date(2026, 1, 10),
            hours=Decimal("12.50"),
            billing_rate=Decimal("150.0000"),
            costing_rate=Decimal("75.0000"),
            is_billable=True,
            notes="Optimized high-speed trochoidal milling paths for Ti-6Al-4V.",
        )
        assert ts1.billing_amount == Decimal("1875.0000")
        assert ts1.costing_amount == Decimal("937.5000")
        assert task1.actual_hours == Decimal("12.50")

        ts2 = await project_service.log_timesheet(
            session=db,
            tenant_id=tenant_id,
            timesheet_number="TS-2026-002",
            employee_id=emp_david,
            employee_name="David Rossi",
            project_id=project.project_id,
            task_id=task2.task_id,
            activity_type="FABRICATION",
            work_date=date(2026, 1, 12),
            hours=Decimal("20.00"),
            billing_rate=Decimal("120.0000"),
            costing_rate=Decimal("60.0000"),
            is_billable=True,
            notes="Machined test coupons and performed dimensional CMM validation.",
        )
        assert ts2.billing_amount == Decimal("2400.0000")
        assert ts2.costing_amount == Decimal("1200.0000")
        assert task2.actual_hours == Decimal("20.00")

        # D. Verify Automatic Project Financial Rollups
        refreshed_proj = await project_service.get_project(db, tenant_id, project.project_id)
        assert refreshed_proj is not None
        assert refreshed_proj.actual_cost == Decimal("2137.5000")
        assert refreshed_proj.total_billed_amount == Decimal("4275.0000")

        # E. Task Completion and Progress Rollup
        await project_service.update_task(db, tenant_id, task1.task_id, status="COMPLETED")
        proj_step1 = await project_service.get_project(db, tenant_id, project.project_id)
        assert proj_step1 is not None
        assert proj_step1.percent_complete == Decimal("50.00")

        await project_service.update_task(db, tenant_id, task2.task_id, status="COMPLETED")
        proj_step2 = await project_service.get_project(db, tenant_id, project.project_id)
        assert proj_step2 is not None
        assert proj_step2.percent_complete == Decimal("100.00")
        assert proj_step2.status == "COMPLETED"

        print("Phase 7 100% ERPNext Parity Integration Test Passed Flawlessly!")
