"""Demo Data Seeder for Exploration & Testing.

Generates realistic seed entities (Items, Customers, Suppliers, PO, GRN, Workstations, Certs)
tailored to the tenant's chosen industry and base currency.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.hr import Employee
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.manufacturing import Workstation
from erp.db.models.operator_cert import OperatorCertificationRecord
from erp.db.models.purchasing import (
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierInvoice,
)
from erp.db.models.sales import Customer


async def seed_demo_data(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    industry: str,
    currency: str,
    primary_warehouse: Warehouse,
) -> None:
    """Seeds full operational data for a newly provisioned tenant."""
    # 1. Seed Industry-Specific Items
    if industry == "Manufacturing":
        items_data = [
            ("RAW-ALUM-6061", "Aerospace Grade 6061 Aluminum Billet", Decimal("45.00"), Decimal("150.00"), "KG", True, True, False),
            ("COMP-TITANIUM-BOLT", "High-Tensile Titanium Bolt M8x40", Decimal("12.50"), Decimal("500.00"), "Nos", True, True, False),
            ("ASSY-BRACKET-WING", "CNC Machined Structural Wing Bracket", Decimal("285.00"), Decimal("20.00"), "Nos", True, False, True),
            ("CHEM-COOLANT-SYN", "Synthetic CNC Cutting Coolant Fluid", Decimal("65.00"), Decimal("10.00"), "Ltr", True, True, False),
        ]
    elif industry in ["Retail", "Wholesale / Distribution"]:
        items_data = [
            ("SKU-PREM-SHIRT-M", "Classic Tailored Oxford Shirt - Medium", Decimal("22.00"), Decimal("50.00"), "Nos", True, True, True),
            ("SKU-DENIM-PANT-32", "Selvedge Raw Denim Jeans - 32W", Decimal("45.00"), Decimal("40.00"), "Nos", True, True, True),
            ("SKU-LEATHER-BELT", "Full-Grain Italian Leather Belt", Decimal("18.00"), Decimal("30.00"), "Nos", True, True, True),
        ]
    elif industry == "Food & Beverage":
        items_data = [
            ("ING-ORGANIC-FLOUR", "Organic Stoneground Wheat Flour", Decimal("1.80"), Decimal("500.00"), "KG", True, True, False),
            ("ING-PURE-CANE-SUGAR", "Fair-Trade Pure Cane Sugar", Decimal("2.20"), Decimal("300.00"), "KG", True, True, False),
            ("PROD-ARTISAN-BREAD", "Artisan Sourdough Loaf 800g", Decimal("4.50"), Decimal("25.00"), "Nos", True, False, True),
        ]
    else:
        items_data = [
            ("ITEM-STD-MATERIAL", "Standard Commercial Material Stock", Decimal("35.00"), Decimal("100.00"), "Nos", True, True, True),
            ("ITEM-FINISHED-UNIT", "Manufactured Final Delivery Assembly", Decimal("150.00"), Decimal("20.00"), "Nos", True, False, True),
        ]

    created_items: list[Item] = []
    for code, name, rate, reorder, uom, is_stock, is_purch, is_sales in items_data:
        it = Item(
            item_id=uuid.uuid4(),
            tenant_id=tenant_id,
            item_code=code,
            item_name=name,
            standard_rate=rate,
            reorder_level=reorder,
            stock_uom=uom,
            is_stock_item=is_stock,
            is_purchase_item=is_purch,
            is_sales_item=is_sales,
            valuation_method="FIFO",
        )
        session.add(it)
        created_items.append(it)

        # Initialize stock level record
        sl = StockLevel(
            tenant_id=tenant_id,
            item_id=it.item_id,
            warehouse_id=primary_warehouse.warehouse_id,
            current_qty=Decimal("100.0000"),
            available_qty=Decimal("100.0000"),
            valuation_rate=rate,
        )
        session.add(sl)

    # 2. Customers
    customers_data = [
        ("CUST-APEX-GLOBAL", "Apex Global Industries Corp.", "contact@apexglobal.com", Decimal("150000.00")),
        ("CUST-VORTEX-TECH", "Vortex Defense & Technologies", "procurement@vortextech.com", Decimal("250000.00")),
    ]
    for code, name, email, credit in customers_data:
        cust = Customer(
            customer_id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_code=code,
            customer_name=name,
            email=email,
            credit_limit=credit,
        )
        session.add(cust)

    # 3. Suppliers
    suppliers_data = [
        ("SUPP-PRECISION-ALLOYS", "Precision Alloys & Raw Materials Ltd.", "TAX-PK-9812", 30),
        ("SUPP-GLOBAL-HARDWARE", "Global Industrial Fasteners Inc.", "TAX-PK-4521", 45),
    ]
    created_suppliers: list[Supplier] = []
    for code, name, tax, terms in suppliers_data:
        supp = Supplier(
            supplier_id=uuid.uuid4(),
            tenant_id=tenant_id,
            supplier_code=code,
            supplier_name=name,
            tax_id=tax,
            currency=currency,
            payment_terms_days=terms,
        )
        session.add(supp)
        created_suppliers.append(supp)

    # 4. Workstations (if manufacturing or production)
    # 4. Workstations (if manufacturing or production)
    if industry in ["Manufacturing", "Food & Beverage", "Construction / Real Estate"]:
        workstations_data = [
            ("WS-CNC-5AXIS", "DMG Mori 5-Axis Precision Milling Center", Decimal("120.00")),
            ("WS-LATHE-AUTO", "Haas Automated CNC Turning Lathe", Decimal("85.00")),
            ("WS-INSPECT-CMM", "Zeiss Coordinate Measuring Machine (CMM)", Decimal("60.00")),
        ]
        for code, name, rate in workstations_data:
            ws = Workstation(
                workstation_id=uuid.uuid4(),
                tenant_id=tenant_id,
                workstation_code=code,
                workstation_name=name,
                hourly_rate=rate,
                is_active=True,
            )
            session.add(ws)

    # 5. Employees & Operator Safety Certifications
    emp1 = Employee(
        employee_id=uuid.uuid4(),
        tenant_id=tenant_id,
        employee_code="EMP-1001",
        first_name="Sarah",
        last_name="Jenkins",
        email="s.jenkins@enterprise.local",
        department="Manufacturing Plant Floor",
        certifications=["CNC_5AXIS_OPERATOR"],
        max_weekly_hours=48,
        is_active=True,
    )
    session.add(emp1)

    cert1 = OperatorCertificationRecord(
        cert_id=uuid.uuid4(),
        tenant_id=tenant_id,
        employee_id=emp1.employee_id,
        employee_code="EMP-1001",
        certification_code="CNC_5AXIS_OPERATOR",
        certification_name="5-Axis CNC Precision Milling Safety License",
        issue_date=date.today() - timedelta(days=90),
        expiry_date=date.today() + timedelta(days=275),
        is_active=True,
    )
    session.add(cert1)
    await session.flush()

    # 6. Seed one completed P2P lifecycle (PO -> GRN -> Invoice)
    if created_suppliers and created_items:
        first_supp = created_suppliers[0]
        first_item = created_items[0]

        po_id = uuid.uuid4()
        po = PurchaseOrder(
            po_id=po_id,
            tenant_id=tenant_id,
            po_number=f"PO-{date.today().year}-001",
            supplier_id=first_supp.supplier_id,
            order_date=date.today() - timedelta(days=7),
            total_amount=Decimal("4500.0000"),
            currency=currency,
            status="FULFILLED",
        )
        session.add(po)

        po_item = PurchaseOrderItem(
            item_line_id=uuid.uuid4(),
            tenant_id=tenant_id,
            po_id=po_id,
            item_id=first_item.item_id,
            quantity=Decimal("100.0000"),
            unit_price=Decimal("45.0000"),
            line_total=Decimal("4500.0000"),
        )
        session.add(po_item)
        await session.flush()

        grn_id = uuid.uuid4()
        grn = GoodsReceiptNote(
            grn_id=grn_id,
            tenant_id=tenant_id,
            grn_number=f"GRN-{date.today().year}-001",
            po_id=po_id,
            supplier_id=first_supp.supplier_id,
            receipt_date=date.today() - timedelta(days=3),
            status="COMPLETED",
        )
        session.add(grn)
        await session.flush()

        inv = SupplierInvoice(
            invoice_id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_number=f"INV-VENDOR-{date.today().year}-9841",
            supplier_id=first_supp.supplier_id,
            po_id=po_id,
            grn_id=grn_id,
            invoice_date=date.today() - timedelta(days=2),
            currency=currency,
            subtotal=Decimal("4500.0000"),
            tax_amount=Decimal("0.0000"),
            total_amount=Decimal("4500.0000"),
            matching_status="MATCHED",
        )
        session.add(inv)
        await session.flush()
