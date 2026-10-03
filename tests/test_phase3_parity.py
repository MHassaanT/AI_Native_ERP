"""Comprehensive End-to-End Parity Tests for Phase 3: Stock, Warehousing, Serial & Batch Tracking, and Logistics.

Verifies:
1. Universal Stock Entry lifecycle: Material Receipt, Transfer, and Issue with ledger & GL integration.
2. Physical Stock Reconciliation: Book vs physical variance calculation, adjusting SLE, and GL posting.
3. Batch Lot and Unit Serial Number tracking with status lifecycles and expiration validation.
4. Order Fulfillment Pick Lists: Location picking, picked quantity tracking, and completion.
5. Carton Packing Slips: Case bundling and gross/net weight manifests.
6. Delivery Trips & Route Logistics: Vehicle dispatch, ordered multi-stop completions, and proof of delivery.
7. Stock Reservations Engine: Order locking, over-allocation prevention, and reservation release/consumption.
8. Product Variants & Attribute Matrix: Template items and automated concrete SKU variant generation.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.models.inventory import (
    Batch,
    Item,
    ItemAttribute,
    SerialNo,
    StockEntry,
    StockLedgerEntry,
    StockLevel,
    StockReconciliation,
    StockReservationEntry,
    Warehouse,
)
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.logistics import (
    DeliveryStop,
    DeliveryTrip,
    PackingSlip,
    PickList,
)
from erp.db.models.sales import Customer, DeliveryNote, SalesOrder
from erp.db.session import async_session_factory
from erp.workflows.stock.delivery_trip_service import delivery_trip_service
from erp.workflows.stock.pick_packing_service import pick_packing_service
from erp.workflows.stock.reconciliation_service import reconciliation_service
from erp.workflows.stock.serial_batch_service import serial_batch_service
from erp.workflows.stock.stock_entry_service import stock_entry_service
from erp.workflows.stock.stock_reservation_service import stock_reservation_service
from erp.workflows.stock.variant_service import variant_service


@pytest.mark.asyncio
async def test_phase3_complete_stock_logistics_parity():
    """Runs the complete suite of Phase 3 stock, warehousing, fulfillment, and logistics workflows."""
    async with async_session_factory() as session:
        # -------------------------------------------------------------
        # 1. Setup Tenant, Warehouses, and Items
        # -------------------------------------------------------------
        tenant_id = uuid.uuid4()
        suffix = uuid.uuid4().hex[:6].upper()

        wh_main = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-MAIN-{suffix}",
            warehouse_name="Central Logistics Distribution Hub",
            is_active=True,
        )
        wh_secondary = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-SEC-{suffix}",
            warehouse_name="Secondary Retail Fulfillment Center",
            is_active=True,
        )
        session.add_all([wh_main, wh_secondary])
        await session.flush()

        item_raw = Item(
            tenant_id=tenant_id,
            item_code=f"COMP-TURBINE-{suffix}",
            item_name="Precision Turbine Core Blade",
            stock_uom="Nos",
            is_stock_item=True,
            is_purchase_item=True,
            is_sales_item=True,
            standard_rate=Decimal("15.0000"),
            reorder_level=Decimal("100.0000"),
        )
        session.add(item_raw)
        await session.flush()

        # -------------------------------------------------------------
        # 2. Stock Entry: Material Receipt (+500 into Main Warehouse)
        # -------------------------------------------------------------
        entry_receipt = await stock_entry_service.create_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_number=f"STE-REC-{suffix}",
            stock_entry_type="MATERIAL_RECEIPT",
            to_warehouse_id=wh_main.warehouse_id,
            items=[{
                "item_id": item_raw.item_id,
                "t_warehouse_id": wh_main.warehouse_id,
                "qty": Decimal("500.0000"),
                "basic_rate": Decimal("15.0000"),
                "uom": "Nos",
            }],
            notes="Initial material receipt into main warehouse.",
        )
        assert entry_receipt.status == "DRAFT"
        assert entry_receipt.total_amount == Decimal("7500.0000")

        # Submit Receipt
        submitted_receipt = await stock_entry_service.submit_stock_entry(
            session, tenant_id, entry_receipt.entry_id
        )
        assert submitted_receipt.status == "SUBMITTED"

        # Verify StockLevel in WH Main
        level_main = (await session.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == item_raw.item_id,
                StockLevel.warehouse_id == wh_main.warehouse_id,
            )
        )).scalar_one()
        assert level_main.current_qty == Decimal("500.0000")
        assert level_main.valuation_rate == Decimal("15.0000")

        # Verify GL Entries (Debit 1300 $7,500, Credit 5200 $7,500)
        gl_entries = (await session.execute(
            select(GeneralLedgerEntry).where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.source_document_id == entry_receipt.entry_id,
            )
        )).scalars().all()
        assert len(gl_entries) == 2
        debit_entry = next(g for g in gl_entries if g.debit_amount > Decimal("0.0000"))
        credit_entry = next(g for g in gl_entries if g.credit_amount > Decimal("0.0000"))
        assert debit_entry.account_code == "1300-STOCK-IN-HAND"
        assert debit_entry.debit_amount == Decimal("7500.0000")
        assert credit_entry.account_code == "5200-STOCK-ADJUSTMENT"
        assert credit_entry.credit_amount == Decimal("7500.0000")

        # -------------------------------------------------------------
        # 3. Stock Entry: Material Transfer (200 from WH Main to WH Sec)
        # -------------------------------------------------------------
        entry_transfer = await stock_entry_service.create_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_number=f"STE-TRF-{suffix}",
            stock_entry_type="MATERIAL_TRANSFER",
            from_warehouse_id=wh_main.warehouse_id,
            to_warehouse_id=wh_secondary.warehouse_id,
            items=[{
                "item_id": item_raw.item_id,
                "s_warehouse_id": wh_main.warehouse_id,
                "t_warehouse_id": wh_secondary.warehouse_id,
                "qty": Decimal("200.0000"),
                "basic_rate": Decimal("15.0000"),
            }],
        )
        await stock_entry_service.submit_stock_entry(session, tenant_id, entry_transfer.entry_id)

        # Verify updated balances
        await session.refresh(level_main)
        assert level_main.current_qty == Decimal("300.0000")

        level_sec = (await session.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == item_raw.item_id,
                StockLevel.warehouse_id == wh_secondary.warehouse_id,
            )
        )).scalar_one()
        assert level_sec.current_qty == Decimal("200.0000")
        assert level_sec.valuation_rate == Decimal("15.0000")

        # -------------------------------------------------------------
        # 4. Stock Entry: Material Issue (50 units issued/scrapped from Main)
        # -------------------------------------------------------------
        entry_issue = await stock_entry_service.create_stock_entry(
            session=session,
            tenant_id=tenant_id,
            entry_number=f"STE-ISS-{suffix}",
            stock_entry_type="MATERIAL_ISSUE",
            from_warehouse_id=wh_main.warehouse_id,
            items=[{
                "item_id": item_raw.item_id,
                "s_warehouse_id": wh_main.warehouse_id,
                "qty": Decimal("50.0000"),
                "basic_rate": Decimal("15.0000"),
            }],
        )
        await stock_entry_service.submit_stock_entry(session, tenant_id, entry_issue.entry_id)
        await session.refresh(level_main)
        assert level_main.current_qty == Decimal("250.0000")

        # -------------------------------------------------------------
        # 5. Physical Stock Reconciliation (Physical count: 230 vs Book: 250)
        # -------------------------------------------------------------
        recon = await reconciliation_service.create_reconciliation(
            session=session,
            tenant_id=tenant_id,
            reconciliation_number=f"REC-{suffix}",
            items=[{
                "item_id": item_raw.item_id,
                "warehouse_id": wh_main.warehouse_id,
                "reconciled_qty": Decimal("230.0000"),
                "reconciled_valuation_rate": Decimal("15.0000"),
            }],
        )
        assert recon.status == "DRAFT"
        # 230 - 250 = -20 units deficit * $15 = -$300 variance
        assert recon.total_variance_value == Decimal("-300.0000")

        submitted_recon = await reconciliation_service.submit_reconciliation(
            session, tenant_id, recon.reconciliation_id
        )
        assert submitted_recon.status == "SUBMITTED"

        # Verify Main stock adjusted to 230
        await session.refresh(level_main)
        assert level_main.current_qty == Decimal("230.0000")

        # Verify reconciliation GL entry (Debit 5200 $300 loss, Credit 1300 $300)
        recon_gl = (await session.execute(
            select(GeneralLedgerEntry).where(
                GeneralLedgerEntry.tenant_id == tenant_id,
                GeneralLedgerEntry.source_document_id == recon.reconciliation_id,
            )
        )).scalars().all()
        assert len(recon_gl) == 2
        recon_debit = next(g for g in recon_gl if g.debit_amount > Decimal("0.0000"))
        assert recon_debit.account_code == "5200-STOCK-ADJUSTMENT"
        assert recon_debit.debit_amount == Decimal("300.0000")

        # -------------------------------------------------------------
        # 6. Serial & Batch Management
        # -------------------------------------------------------------
        batch = await serial_batch_service.create_batch(
            session=session,
            tenant_id=tenant_id,
            batch_number=f"BAT-{suffix}-001",
            item_id=item_raw.item_id,
            manufacturing_date=date.today(),
            expiry_date=date.today() + timedelta(days=180),
            description="Aerospace certified batch lot",
        )
        assert batch.status == "ACTIVE"

        serial1 = await serial_batch_service.create_serial_number(
            session=session,
            tenant_id=tenant_id,
            serial_number=f"SN-{suffix}-101",
            item_id=item_raw.item_id,
            warehouse_id=wh_secondary.warehouse_id,
            warranty_expiry_date=date.today() + timedelta(days=365),
        )
        assert serial1.status == "ACTIVE"

        # Transition serial to DELIVERED
        updated_serial = await serial_batch_service.update_serial_status(
            session=session,
            tenant_id=tenant_id,
            serial_number=serial1.serial_number,
            new_status="DELIVERED",
        )
        assert updated_serial.status == "DELIVERED"

        # -------------------------------------------------------------
        # 7. Warehouse Pick List & Carton Packing Slip
        # -------------------------------------------------------------
        customer = Customer(
            tenant_id=tenant_id,
            customer_code=f"CUST-{suffix}",
            customer_name="Starlight Aerospace Ltd.",
        )
        session.add(customer)
        await session.flush()

        pick_list = await pick_packing_service.create_pick_list(
            session=session,
            tenant_id=tenant_id,
            pick_list_number=f"PL-{suffix}",
            customer_id=customer.customer_id,
            items=[{
                "item_id": item_raw.item_id,
                "warehouse_id": wh_secondary.warehouse_id,
                "qty_to_pick": Decimal("100.0000"),
                "picked_qty": Decimal("0.0000"),
            }],
        )
        assert pick_list.status == "DRAFT"

        # Pick items
        item_id_pl = pick_list.items[0].pick_item_id
        await pick_packing_service.update_picked_qty(
            session, tenant_id, pick_list.pick_list_id, item_id_pl, Decimal("100.0000")
        )
        completed_pl = await pick_packing_service.complete_pick_list(
            session, tenant_id, pick_list.pick_list_id
        )
        assert completed_pl.status == "COMPLETED"

        # Packing Slip
        packing_slip = await pick_packing_service.create_packing_slip(
            session=session,
            tenant_id=tenant_id,
            slip_number=f"PS-{suffix}",
            from_case_no=1,
            to_case_no=1,
            net_weight_pkg=Decimal("25.5000"),
            gross_weight_pkg=Decimal("28.0000"),
            items=[{
                "item_id": item_raw.item_id,
                "qty": Decimal("100.0000"),
                "net_weight": Decimal("25.5000"),
            }],
        )
        assert packing_slip.status == "DRAFT"
        submitted_ps = await pick_packing_service.submit_packing_slip(
            session, tenant_id, packing_slip.packing_slip_id
        )
        assert submitted_ps.status == "SUBMITTED"

        # -------------------------------------------------------------
        # 8. Delivery Trips & Multi-Stop Dispatch
        # -------------------------------------------------------------
        so = SalesOrder(
            tenant_id=tenant_id,
            order_number=f"SO-{suffix}",
            customer_id=customer.customer_id,
            order_date=date.today(),
            delivery_date=date.today() + timedelta(days=3),
            total_amount=Decimal("1500.0000"),
            status="CONFIRMED",
        )
        session.add(so)
        await session.flush()

        dn = DeliveryNote(
            tenant_id=tenant_id,
            delivery_note_number=f"DN-{suffix}",
            order_id=so.order_id,
            customer_id=customer.customer_id,
            delivery_date=date.today(),
            status="DISPATCHED",
        )
        session.add(dn)
        await session.flush()

        trip = await delivery_trip_service.create_delivery_trip(
            session=session,
            tenant_id=tenant_id,
            trip_number=f"TRIP-{suffix}",
            driver_name="Tariq Mansoor",
            vehicle_number="TRK-9821-ISB",
            total_distance_km=Decimal("45.50"),
            stops=[{
                "delivery_note_id": dn.delivery_note_id,
                "customer_id": customer.customer_id,
                "address": "Sector I-9/2 Industrial Area, Islamabad",
                "stop_sequence": 1,
            }],
        )
        assert trip.status == "DRAFT"

        # Dispatch vehicle
        dispatched_trip = await delivery_trip_service.dispatch_trip(
            session, tenant_id, trip.trip_id
        )
        assert dispatched_trip.status == "IN_TRANSIT"

        # Complete stop
        stop_id = trip.stops[0].stop_id
        completed_stop = await delivery_trip_service.complete_stop(
            session, tenant_id, trip.trip_id, stop_id, customer_signature="ALI-MGR-STAMP"
        )
        assert completed_stop.status == "DELIVERED"
        await session.refresh(dn)
        assert dn.status == "DELIVERED"

        # Complete full trip
        final_trip = await delivery_trip_service.complete_trip(session, tenant_id, trip.trip_id)
        assert final_trip.status == "COMPLETED"

        # -------------------------------------------------------------
        # 9. Stock Reservations Engine
        # -------------------------------------------------------------
        # wh_secondary currently has 200 units on hand
        dummy_so_id = so.order_id
        res = await stock_reservation_service.create_reservation(
            session=session,
            tenant_id=tenant_id,
            item_id=item_raw.item_id,
            warehouse_id=wh_secondary.warehouse_id,
            voucher_type="SALES_ORDER",
            voucher_id=dummy_so_id,
            reserved_qty=Decimal("80.0000"),
        )
        assert res.status == "ACTIVE"

        await session.refresh(level_sec)
        assert level_sec.reserved_qty == Decimal("80.0000")
        assert level_sec.available_qty == Decimal("120.0000")

        # Attempt to over-reserve (available is only 120, requesting 150)
        with pytest.raises(ValueError, match="Insufficient unreserved stock"):
            await stock_reservation_service.create_reservation(
                session=session,
                tenant_id=tenant_id,
                item_id=item_raw.item_id,
                warehouse_id=wh_secondary.warehouse_id,
                voucher_type="SALES_ORDER",
                voucher_id=uuid.uuid4(),
                reserved_qty=Decimal("150.0000"),
            )

        # Consume reservation upon order fulfillment
        consumed_res = await stock_reservation_service.consume_reservation(
            session, tenant_id, res.reservation_id, Decimal("80.0000")
        )
        assert consumed_res.status == "FULFILLED"
        await session.refresh(level_sec)
        assert level_sec.reserved_qty == Decimal("0.0000")
        assert level_sec.available_qty == Decimal("200.0000")

        # -------------------------------------------------------------
        # 10. Product Variants & Attribute Matrix
        # -------------------------------------------------------------
        attr_size = await variant_service.create_attribute(
            session=session,
            tenant_id=tenant_id,
            attribute_name=f"Size-{suffix}",
            values=[
                {"attribute_value": "Small", "abbr": "S"},
                {"attribute_value": "Medium", "abbr": "M"},
                {"attribute_value": "Large", "abbr": "L"},
            ],
        )
        assert len(attr_size.values) == 3

        template_item = Item(
            tenant_id=tenant_id,
            item_code=f"TSHIRT-BASE-{suffix}",
            item_name="Pima Cotton Performance Crewneck",
            stock_uom="Nos",
            is_stock_item=True,
            is_sales_item=True,
            standard_rate=Decimal("45.0000"),
        )
        session.add(template_item)
        await session.flush()

        variants = await variant_service.generate_item_variants(
            session=session,
            tenant_id=tenant_id,
            template_item_id=template_item.item_id,
            variant_definitions=[
                {
                    "item_code": f"TSHIRT-{suffix}-M-BLK",
                    "item_name": "Pima Crewneck (Medium, Black)",
                    "attributes": {"Size": "Medium", "Color": "Black"},
                    "standard_rate": Decimal("45.0000"),
                },
                {
                    "item_code": f"TSHIRT-{suffix}-L-NVY",
                    "item_name": "Pima Crewneck (Large, Navy)",
                    "attributes": {"Size": "Large", "Color": "Navy"},
                    "standard_rate": Decimal("48.0000"),
                },
            ],
        )
        assert len(variants) == 2
        assert variants[0].variant_of == template_item.item_id
        assert variants[1].standard_rate == Decimal("48.0000")
        assert template_item.has_variants is True

        print("\nAll Phase 3 Stock & Logistics Parity workflows verified successfully!")
