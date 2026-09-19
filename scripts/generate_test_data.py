"""Synthetic Test Data Generator for AI-Native ERP."""

import asyncio
from decimal import Decimal

from erp.config import settings
from erp.db.models.hr import Employee
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.manufacturing import BOM, BOMItem, Workstation
from erp.db.models.purchasing import Supplier
from erp.db.models.sales import Customer
from erp.db.session import async_session_factory


async def generate_synthetic_data():
    tenant_id = settings.DEFAULT_TENANT_ID
    print(f"Generating synthetic enterprise dataset for tenant {tenant_id}...")

    async with async_session_factory() as session:
        # 1. Warehouses
        wh_raw = Warehouse(
            tenant_id=tenant_id,
            warehouse_code="WH-RAW-01",
            warehouse_name="Raw Materials Central Warehouse",
            is_quarantine=False,
        )
        wh_quarantine = Warehouse(
            tenant_id=tenant_id,
            warehouse_code="WH-QUARANTINE-01",
            warehouse_name="Incoming Quality Inspection Quarantine",
            is_quarantine=True,
        )
        wh_fg = Warehouse(
            tenant_id=tenant_id,
            warehouse_code="WH-FG-01",
            warehouse_name="Finished Goods Distribution Center",
            is_quarantine=False,
        )
        session.add_all([wh_raw, wh_quarantine, wh_fg])
        await session.flush()

        # 2. Items
        item_resin = Item(
            tenant_id=tenant_id,
            item_code="RAW-RESIN-HDPE",
            item_name="High-Density Polyethylene Resin Pellet",
            stock_uom="Kg",
            is_purchase_item=True,
            is_stock_item=True,
            is_sales_item=False,
            standard_rate=Decimal("2.4500"),
            reorder_level=Decimal("5000.0000"),
        )
        item_casing = Item(
            tenant_id=tenant_id,
            item_code="FG-ENCLOSURE-IP67",
            item_name="Industrial IP67 Electrical Enclosure",
            stock_uom="Nos",
            is_purchase_item=False,
            is_stock_item=True,
            is_sales_item=True,
            standard_rate=Decimal("48.5000"),
            reorder_level=Decimal("200.0000"),
        )
        session.add_all([item_resin, item_casing])
        await session.flush()

        # 3. Stock Level
        stock_resin = StockLevel(
            tenant_id=tenant_id,
            item_id=item_resin.item_id,
            warehouse_id=wh_raw.warehouse_id,
            current_qty=Decimal("12500.0000"),
            available_qty=Decimal("12500.0000"),
            valuation_rate=Decimal("2.4500"),
        )
        session.add(stock_resin)

        # 4. Supplier
        supplier = Supplier(
            tenant_id=tenant_id,
            supplier_code="SUP-POLYMERS-GLOBAL",
            supplier_name="Global Polymers Inc.",
            tax_id="US-EIN-98-7654321",
            payment_terms_days=30,
            otif_score=Decimal("96.50"),
        )
        session.add(supplier)
        await session.flush()

        # 5. Customer
        customer = Customer(
            tenant_id=tenant_id,
            customer_code="CUST-SIEMENS-ENERGY",
            customer_name="Siemens Energy AG",
            email="procurement@siemens-energy.com",
            credit_limit=Decimal("250000.0000"),
            lifetime_value=Decimal("1420000.0000"),
        )
        session.add(customer)
        await session.flush()

        # 6. Workstation
        workstation = Workstation(
            tenant_id=tenant_id,
            workstation_code="WS-INJECTION-01",
            workstation_name="Engel 500T Hydraulic Injection Molder",
            hourly_rate=Decimal("120.0000"),
            status="OPERATIONAL",
            iot_device_id="IOT-ENGEL-500-01",
            health_score=Decimal("94.20"),
        )
        session.add(workstation)
        await session.flush()

        # 7. BOM
        bom = BOM(
            tenant_id=tenant_id,
            bom_number="BOM-ENCLOSURE-V1",
            item_id=item_casing.item_id,
            quantity=Decimal("1.0000"),
            total_cost=Decimal("14.7000"),
        )
        session.add(bom)
        await session.flush()

        bom_line = BOMItem(
            tenant_id=tenant_id,
            bom_id=bom.bom_id,
            item_id=item_resin.item_id,
            quantity=Decimal("6.0000"),  # 6 kg resin per enclosure
            rate=Decimal("2.4500"),
            amount=Decimal("14.7000"),
        )
        session.add(bom_line)

        # 8. Employee
        employee = Employee(
            tenant_id=tenant_id,
            employee_code="EMP-1042",
            first_name="Marcus",
            last_name="Vance",
            email="m.vance@factory.internal",
            department="PLASTICS_MANUFACTURING",
            certifications=["INJECTION_MOLDING_L3", "OSHA_SAFETY_2026", "LOCKOUT_TAGOUT"],
            max_weekly_hours=48,
        )
        session.add(employee)

        await session.commit()
        print("Synthetic enterprise dataset generated successfully.")


if __name__ == "__main__":
    asyncio.run(generate_synthetic_data())
