"""Master Onboarding Checklist Steps and Real Database Validation Rules.

Each step actually queries the underlying PostgreSQL models to verify real records exist.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.hr import Employee, ShiftSchedule
from erp.db.models.inventory import Item, Warehouse
from erp.db.models.ledger import Account, FiscalPeriod, GeneralLedgerEntry
from erp.db.models.manufacturing import BOM, MaintenanceTicket, WorkOrder, Workstation
from erp.db.models.operator_cert import OperatorCertificationRecord
from erp.db.models.purchasing import GoodsReceiptNote, PurchaseOrder, Supplier, SupplierInvoice
from erp.db.models.sales import Customer, SalesQuotation


MASTER_MODULE_STEPS: dict[str, list[dict[str, Any]]] = {
    "accounting": [
        {
            "step_key": "review_chart_of_accounts",
            "step_title": "Review Chart of Accounts",
            "step_description": "Verify localized double-entry account tree created during setup.",
            "action_type": "VIEW_REPORT",
            "reference_entity": "Account",
            "target_route": "/ledger",
            "sort_order": 1,
        },
        {
            "step_key": "create_first_journal",
            "step_title": "Stage Double-Entry Journal",
            "step_description": "Post a balanced zero-sum journal entry to test ledger invariants.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "GeneralLedgerEntry",
            "target_route": "/ledger",
            "sort_order": 2,
        },
        {
            "step_key": "review_fiscal_periods",
            "step_title": "Verify Fiscal Calendar & Periods",
            "step_description": "Ensure 12-month fiscal calendar was correctly locked/unlocked.",
            "action_type": "CONFIGURE_SETTING",
            "reference_entity": "FiscalPeriod",
            "target_route": "/ledger",
            "sort_order": 3,
        },
    ],
    "inventory": [
        {
            "step_key": "setup_warehouse",
            "step_title": "Verify Warehouse Layout",
            "step_description": "Confirm primary warehouse and quarantine locations are operational.",
            "action_type": "VIEW_REPORT",
            "reference_entity": "Warehouse",
            "target_route": "/inventory",
            "sort_order": 1,
        },
        {
            "step_key": "create_first_item",
            "step_title": "Register Catalog Item (SKU)",
            "step_description": "Create raw material or finished product with standard rate & UOM.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "Item",
            "target_route": "/inventory",
            "sort_order": 2,
        },
        {
            "step_key": "calculate_rop",
            "step_title": "Calculate Stochastic Reorder Point (ROP)",
            "step_description": "Run dynamic safety stock calculator for inventory replenishment.",
            "action_type": "VIEW_REPORT",
            "reference_entity": "Item",
            "target_route": "/inventory",
            "sort_order": 3,
        },
    ],
    "commercial": [
        {
            "step_key": "create_first_customer",
            "step_title": "Register Trade Customer",
            "step_description": "Add your first corporate buyer with credit terms and tax identifier.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "Customer",
            "target_route": "/commercial",
            "sort_order": 1,
        },
        {
            "step_key": "create_first_quote",
            "step_title": "Generate Defended Sales Quote",
            "step_description": "Create quotation with 22% minimum contribution margin defense.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "SalesQuotation",
            "target_route": "/commercial",
            "sort_order": 2,
        },
        {
            "step_key": "test_dynamic_pricing",
            "step_title": "Test BOM Dynamic Landed Costing",
            "step_description": "Verify machine depreciation, labor and freight rollup calculator.",
            "action_type": "VIEW_REPORT",
            "reference_entity": "SalesQuotation",
            "target_route": "/commercial",
            "sort_order": 3,
        },
    ],
    "accounts_payable": [
        {
            "step_key": "create_supplier",
            "step_title": "Register Trade Vendor / Supplier",
            "step_description": "Add component vendor with tax ID and payment terms.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "Supplier",
            "target_route": "/accounts-payable",
            "sort_order": 1,
        },
        {
            "step_key": "create_purchase_order",
            "step_title": "Issue Purchase Order (PO)",
            "step_description": "Create binding vendor purchase order for inventory replenishment.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "PurchaseOrder",
            "target_route": "/accounts-payable",
            "sort_order": 2,
        },
        {
            "step_key": "create_grn",
            "step_title": "Receive Goods (GRN)",
            "step_description": "Log physical dock delivery note updating warehouse stock ledger.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "GoodsReceiptNote",
            "target_route": "/accounts-payable",
            "sort_order": 3,
        },
        {
            "step_key": "run_three_way_match",
            "step_title": "Execute Touchless 3-Way Match",
            "step_description": "Match PO vs GRN vs Vendor Invoice within tolerance ceilings.",
            "action_type": "VIEW_REPORT",
            "reference_entity": "SupplierInvoice",
            "target_route": "/accounts-payable",
            "sort_order": 4,
        },
    ],
    "production": [
        {
            "step_key": "create_workstation",
            "step_title": "Register Factory Workstation",
            "step_description": "Configure CNC, molding machine or assembly cell with hourly rate.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "Workstation",
            "target_route": "/production",
            "sort_order": 1,
        },
        {
            "step_key": "create_bom",
            "step_title": "Create Bill of Materials (BOM)",
            "step_description": "Define engineering multi-level subassemblies and required materials.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "BOM",
            "target_route": "/production",
            "sort_order": 2,
        },
        {
            "step_key": "create_work_order",
            "step_title": "Launch Production Work Order",
            "step_description": "Schedule production lot and solve makespan with CP-SAT solver.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "WorkOrder",
            "target_route": "/production",
            "sort_order": 3,
        },
    ],
    "workforce": [
        {
            "step_key": "create_employee",
            "step_title": "Add Shop Floor Operator / Staff",
            "step_description": "Register workforce employee with department and contact details.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "Employee",
            "target_route": "/workforce",
            "sort_order": 1,
        },
        {
            "step_key": "add_certification",
            "step_title": "Record Safety Certification",
            "step_description": "Issue machine operator safety license required for factory shifts.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "OperatorCertificationRecord",
            "target_route": "/workforce",
            "sort_order": 2,
        },
        {
            "step_key": "create_shift",
            "step_title": "Schedule Compliant Work Shift",
            "step_description": "Schedule shifts enforcing 11h EU rest invariant and 48h weekly cap.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "ShiftSchedule",
            "target_route": "/workforce",
            "sort_order": 3,
        },
    ],
    "quality": [
        {
            "step_key": "view_telemetry",
            "step_title": "Inspect Edge Quality Stream",
            "step_description": "Monitor optical camera feed, defect rate & rolling 1,000-unit stats.",
            "action_type": "VIEW_REPORT",
            "reference_entity": None,
            "target_route": "/quality",
            "sort_order": 1,
        },
        {
            "step_key": "run_optical_inspection",
            "step_title": "Simulate PLC Scrap Trip",
            "step_description": "Inject surface crack or dimension defect to test <200ms diverter trip.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": None,
            "target_route": "/quality",
            "sort_order": 2,
        },
    ],
    "maintenance": [
        {
            "step_key": "create_ticket",
            "step_title": "Log Machine Maintenance Ticket",
            "step_description": "Create preventative or corrective maintenance work ticket.",
            "action_type": "CREATE_ENTRY",
            "reference_entity": "MaintenanceTicket",
            "target_route": "/maintenance",
            "sort_order": 1,
        },
        {
            "step_key": "simulate_anomaly",
            "step_title": "Test IoT Telemetry Anomaly",
            "step_description": "Simulate vibration/thermal spike to trigger auto-ticket generation.",
            "action_type": "VIEW_REPORT",
            "reference_entity": None,
            "target_route": "/maintenance",
            "sort_order": 2,
        },
    ],
}


async def validate_step_completion(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    step_key: str,
) -> bool:
    """Queries underlying database tables to determine whether a step is fulfilled by real records."""
    if step_key == "review_chart_of_accounts":
        count = await db.scalar(
            select(func.count()).select_from(Account).where(Account.tenant_id == tenant_id)
        )
        return (count or 0) >= 5

    if step_key == "create_first_journal":
        count = await db.scalar(
            select(func.count()).select_from(GeneralLedgerEntry).where(GeneralLedgerEntry.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "review_fiscal_periods":
        count = await db.scalar(
            select(func.count()).select_from(FiscalPeriod).where(FiscalPeriod.tenant_id == tenant_id)
        )
        return (count or 0) >= 12

    if step_key == "setup_warehouse":
        count = await db.scalar(
            select(func.count()).select_from(Warehouse).where(Warehouse.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_first_item":
        count = await db.scalar(
            select(func.count()).select_from(Item).where(Item.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "calculate_rop":
        # Complete if item exists with reorder level
        count = await db.scalar(
            select(func.count()).select_from(Item).where(Item.tenant_id == tenant_id, Item.reorder_level > 0)
        )
        return (count or 0) > 0

    if step_key == "create_first_customer":
        count = await db.scalar(
            select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_first_quote":
        count = await db.scalar(
            select(func.count()).select_from(SalesQuotation).where(SalesQuotation.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "test_dynamic_pricing":
        # If quote exists, dynamic pricing was exercised
        count = await db.scalar(
            select(func.count()).select_from(SalesQuotation).where(SalesQuotation.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_supplier":
        count = await db.scalar(
            select(func.count()).select_from(Supplier).where(Supplier.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_purchase_order":
        count = await db.scalar(
            select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_grn":
        count = await db.scalar(
            select(func.count()).select_from(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "run_three_way_match":
        count = await db.scalar(
            select(func.count()).select_from(SupplierInvoice).where(
                SupplierInvoice.tenant_id == tenant_id,
                SupplierInvoice.matching_status.in_(["MATCHED", "TOLERANCE_APPROVED"]),
            )
        )
        return (count or 0) > 0

    if step_key == "create_workstation":
        count = await db.scalar(
            select(func.count()).select_from(Workstation).where(Workstation.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_bom":
        count = await db.scalar(
            select(func.count()).select_from(BOM).where(BOM.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_work_order":
        count = await db.scalar(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_employee":
        count = await db.scalar(
            select(func.count()).select_from(Employee).where(Employee.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "add_certification":
        count = await db.scalar(
            select(func.count()).select_from(OperatorCertificationRecord).where(OperatorCertificationRecord.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_shift":
        count = await db.scalar(
            select(func.count()).select_from(ShiftSchedule).where(ShiftSchedule.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    if step_key == "create_ticket":
        count = await db.scalar(
            select(func.count()).select_from(MaintenanceTicket).where(MaintenanceTicket.tenant_id == tenant_id)
        )
        return (count or 0) > 0

    return False
