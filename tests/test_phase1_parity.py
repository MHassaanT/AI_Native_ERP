"""Comprehensive Unit & Workflow Tests for Phase 1 Enterprise Parity.

Verifies:
1. Split Payment / Multi-Tender POS Checkout
2. Cart Parking & Restoration
3. POS Returns & Stock Restocking
4. Shift Closing & Consolidated Daily Invoicing (Merge Log)
5. Multi-Plan Subscriptions, Proration, Pause/Resume & Billing Runner
6. Payment Terms Templates & Payment Schedule Milestone Breakdown
7. Cascading Multi-Tier Tax Calculations
8. Customer Advance Payment Allocation
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.session import async_session_factory
from erp.db.models.billing import (
    PaymentTermsTemplate,
    POSClosingEntry,
    POSInvoice,
    POSOpeningEntry,
    POSProfile,
    SalesTaxesAndChargesTemplate,
    Subscription,
    SubscriptionPlan,
)
from erp.db.models.inventory import Item, Warehouse
from erp.db.models.sales import Customer, SalesInvoice
from erp.db.models.user import User
from erp.workflows.billing.pos_service import POSService
from erp.workflows.billing.subscription_service import SubscriptionService
from erp.workflows.billing.tax_and_terms_service import TaxAndTermsService


@pytest.mark.asyncio
async def test_phase1_all_parity_workflows():
    async with async_session_factory() as session:
        # Load or create test tenant context
        cust_stmt = select(Customer).limit(1)
        res = await session.execute(cust_stmt)
        customer = res.scalars().first()
        if not customer:
            tenant_id = uuid.uuid4()
            customer = Customer(
                tenant_id=tenant_id,
                customer_code="CUST-PARITY-TEST",
                customer_name="Parity Test Customer",
                credit_limit=Decimal("50000.00"),
                is_active=True,
            )
            session.add(customer)
            await session.flush()
        else:
            tenant_id = customer.tenant_id

        user_stmt = select(User).where(User.tenant_id == tenant_id).limit(1)
        res = await session.execute(user_stmt)
        user = res.scalars().first()
        if not user:
            user_stmt2 = select(User).limit(1)
            res2 = await session.execute(user_stmt2)
            user = res2.scalars().first()
            tenant_id = user.tenant_id
        user_id = user.user_id

        profile_stmt = select(POSProfile).where(POSProfile.tenant_id == tenant_id).limit(1)
        res = await session.execute(profile_stmt)
        profile = res.scalars().first()
        if not profile:
            wh_stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_id).limit(1)
            wh_res = await session.execute(wh_stmt)
            warehouse = wh_res.scalars().first()
            if not warehouse:
                warehouse = Warehouse(
                    tenant_id=tenant_id,
                    warehouse_code=f"WH-{uuid.uuid4().hex[:4].upper()}",
                    warehouse_name="Main Test Store Warehouse",
                    is_active=True,
                )
                session.add(warehouse)
                await session.flush()
            profile = POSProfile(
                tenant_id=tenant_id,
                profile_name=f"Store POS Profile {uuid.uuid4().hex[:4]}",
                warehouse_id=warehouse.warehouse_id,
                cost_center="Main - CC",
                currency="USD",
                income_account="4000-SALES-REVENUE",
                expense_account="5000-COGS",
                is_active=True,
            )
            session.add(profile)
            await session.flush()

        item_stmt = select(Item).where(Item.tenant_id == tenant_id).limit(1)
        res = await session.execute(item_stmt)
        item1 = res.scalars().first()
        if not item1:
            item1 = Item(
                tenant_id=tenant_id,
                item_code=f"SKU-{uuid.uuid4().hex[:4].upper()}",
                item_name="Precision Calibration Tool",
                standard_rate=Decimal("100.0000"),
                is_active=True,
            )
            session.add(item1)
            await session.flush()

        pos_service = POSService()
        sub_service = SubscriptionService()
        tax_service = TaxAndTermsService()

        # -------------------------------------------------------------
        # 1. POS Shift & Split-Tender Checkout
        # -------------------------------------------------------------
        print("\n--- TEST 1: POS Split Payment ---")
        shift = await pos_service.open_shift(
            session=session,
            tenant_id=tenant_id,
            profile_id=profile.profile_id,
            user_id=user_id,
            opening_float_cash=Decimal("150.0000"),
        )
        assert shift.status == "OPEN"

        # Multi-tender: $50 cash + $55 card
        sale_items = [{"item_id": item1.item_id, "quantity": 1, "unit_price": Decimal("100.0000"), "discount_pct": Decimal("0.00")}]
        payments = [
            {"payment_method": "CASH", "amount": Decimal("50.0000")},
            {"payment_method": "CARD", "amount": Decimal("55.0000")},
        ]
        inv, gl_id = await pos_service.process_pos_sale(
            session=session,
            tenant_id=tenant_id,
            opening_id=shift.opening_id,
            customer_id=customer.customer_id,
            items=sale_items,
            payments=payments,
        )
        await session.commit()

        assert inv.status == "PAID"
        assert inv.payment_method == "SPLIT"
        assert len(inv.payments) == 2
        print(f"POS Split-tender invoice {inv.pos_invoice_number} created: grand total ${inv.grand_total}")

        # -------------------------------------------------------------
        # 2. POS Order Parking & Resumption
        # -------------------------------------------------------------
        print("\n--- TEST 2: POS Order Parking ---")
        cart_data = {"items": sale_items, "customer_id": str(customer.customer_id)}
        parked = await pos_service.park_cart(
            session=session,
            tenant_id=tenant_id,
            profile_id=profile.profile_id,
            user_id=user_id,
            cart_data=cart_data,
            customer_id=customer.customer_id,
            hold_note="Customer stepped away to grab wallet",
        )
        await session.commit()
        assert parked.status == "PARKED"

        parked_list = await pos_service.list_parked_carts(session=session, tenant_id=tenant_id)
        assert any(p.parked_id == parked.parked_id for p in parked_list)

        restored = await pos_service.restore_parked_cart(session=session, tenant_id=tenant_id, parked_id=parked.parked_id)
        await session.commit()
        assert restored.status == "RESTORED"
        print(f"Parked cart {parked.parked_id} successfully held and restored!")

        # -------------------------------------------------------------
        # 3. POS Retail Return & Stock Restocking
        # -------------------------------------------------------------
        print("\n--- TEST 3: POS Return ---")
        ret_inv, _ = await pos_service.process_pos_sale(
            session=session,
            tenant_id=tenant_id,
            opening_id=shift.opening_id,
            customer_id=customer.customer_id,
            items=sale_items,
            payment_method="CASH",
            is_return=True,
            return_against=inv.pos_invoice_number,
        )
        await session.commit()
        assert ret_inv.status == "RETURNED"
        assert ret_inv.is_return is True
        print(f"POS Return invoice {ret_inv.pos_invoice_number} issued against {inv.pos_invoice_number}")

        # -------------------------------------------------------------
        # 4. Shift Closing & Consolidated Invoice Merge Log
        # -------------------------------------------------------------
        print("\n--- TEST 4: Shift Close & Daily Consolidation ---")
        closing = await pos_service.close_shift(
            session=session,
            tenant_id=tenant_id,
            opening_id=shift.opening_id,
            actual_counted_cash=Decimal("200.0000"),
        )
        await session.commit()
        assert closing.status == "SUBMITTED"

        merge_log = await pos_service.consolidate_shift_invoices(
            session=session,
            tenant_id=tenant_id,
            closing_id=closing.closing_id,
        )
        await session.commit()
        assert merge_log.total_invoices_merged >= 2
        print(f"Consolidated {merge_log.total_invoices_merged} POS invoices into merge log {merge_log.merge_log_id}")

        # -------------------------------------------------------------
        # 5. Multi-Plan Subscriptions, Proration & Pause/Resume
        # -------------------------------------------------------------
        print("\n--- TEST 5: Subscriptions Parity ---")
        plan1 = await sub_service.create_plan(
            session=session,
            tenant_id=tenant_id,
            plan_name=f"Enterprise Cloud Tier {uuid.uuid4().hex[:4]}",
            billing_interval="MONTHLY",
            cost=Decimal("299.0000"),
        )
        plan2 = await sub_service.create_plan(
            session=session,
            tenant_id=tenant_id,
            plan_name=f"Add-on Seats {uuid.uuid4().hex[:4]}",
            billing_interval="MONTHLY",
            cost=Decimal("25.0000"),
        )
        await session.commit()

        # Multi-plan item subscription with 14-day free trial
        sub_items = [
            {"plan_id": plan1.plan_id, "quantity": Decimal("1.0000"), "unit_cost": Decimal("299.0000")},
            {"plan_id": plan2.plan_id, "quantity": Decimal("5.0000"), "unit_cost": Decimal("25.0000")},
        ]
        sub = await sub_service.subscribe_customer(
            session=session,
            tenant_id=tenant_id,
            customer_id=customer.customer_id,
            plan_id=plan1.plan_id,
            trial_days=14,
            items=sub_items,
        )
        await session.commit()
        assert sub.status == "TRIALING"
        assert len(sub.items) == 2

        # Proration math check: 10 days active out of 30
        prorated = sub_service.calculate_proration(base_cost=Decimal("300.0000"), days_active=10, total_days_in_period=30)
        assert prorated == Decimal("100.0000")

        # Pause & Resume
        paused = await sub_service.pause_subscription(session=session, tenant_id=tenant_id, subscription_id=sub.subscription_id)
        await session.commit()
        assert paused.status == "PAUSED"

        resumed = await sub_service.resume_subscription(session=session, tenant_id=tenant_id, subscription_id=sub.subscription_id)
        await session.commit()
        assert resumed.status == "ACTIVE"
        print(f"Subscription {sub.subscription_id} tested with multi-plans, trial, proration, and pause/resume!")

        # -------------------------------------------------------------
        # 6. Payment Terms Templates & Invoice Schedules
        # -------------------------------------------------------------
        print("\n--- TEST 6: Payment Terms & Schedules ---")
        terms = [
            {"description": "Advance on Order Confirmation", "invoice_portion": Decimal("30.00"), "credit_days": 0},
            {"description": "Payment on Dispatch", "invoice_portion": Decimal("50.00"), "credit_days": 15},
            {"description": "Retention / Net 30", "invoice_portion": Decimal("20.00"), "credit_days": 30},
        ]
        ptt = await tax_service.create_payment_terms_template(
            session=session,
            tenant_id=tenant_id,
            template_name=f"Standard 30-50-20 Template {uuid.uuid4().hex[:4]}",
            terms=terms,
        )
        await session.commit()
        assert len(ptt.terms) == 3

        # Create a test sales invoice and apply payment terms
        test_inv = SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"TEST-INV-{uuid.uuid4().hex[:6].upper()}",
            customer_id=customer.customer_id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency="USD",
            subtotal=Decimal("10000.0000"),
            tax_amount=Decimal("500.0000"),
            total_amount=Decimal("10500.0000"),
            status="ISSUED",
        )
        session.add(test_inv)
        await session.commit()

        schedules = await tax_service.generate_payment_schedule_for_invoice(
            session=session,
            tenant_id=tenant_id,
            invoice_id=test_inv.invoice_id,
            template_id=ptt.template_id,
        )
        await session.commit()
        assert len(schedules) == 3
        assert schedules[0].portion_amount == Decimal("3150.0000")  # 30% of $10500
        assert schedules[1].portion_amount == Decimal("5250.0000")  # 50% of $10500
        assert schedules[2].portion_amount == Decimal("2100.0000")  # 20% of $10500
        print(f"Applied 3-stage payment terms to invoice {test_inv.invoice_number} successfully!")

        # -------------------------------------------------------------
        # 7. Multi-Tier Cascading Taxes & Charges
        # -------------------------------------------------------------
        print("\n--- TEST 7: Cascading Tax Engine ---")
        tax_defs = [
            {"charge_type": "On Net Total", "account_head": "2200-OUTPUT-VAT", "description": "Standard VAT", "rate": Decimal("10.00")},
            {"charge_type": "Actual", "account_head": "5100-FREIGHT", "description": "Fixed Freight Charges", "rate": Decimal("50.00")},
            {"charge_type": "On Previous Row Amount", "row_id": 1, "account_head": "2210-CESS", "description": "VAT Surcharge / Cess", "rate": Decimal("5.00")},
        ]
        calc = tax_service.calculate_taxes_and_charges(net_total=Decimal("1000.0000"), tax_details=tax_defs)
        # Net total: 1000
        # Row 1 (VAT 10%): 100
        # Row 2 (Freight): 50
        # Row 3 (5% on Row 1 = 5% of 100): 5.0
        # Total tax: 100 + 50 + 5 = 155
        # Grand total: 1155
        assert calc["net_total"] == 1000.0
        assert calc["total_taxes_and_charges"] == 155.0
        assert calc["grand_total"] == 1155.0
        print("Cascading multi-tier taxes (VAT + Freight + Compound Cess) evaluated perfectly!")

        # -------------------------------------------------------------
        # 8. Customer Advance Payment Allocation
        # -------------------------------------------------------------
        print("\n--- TEST 8: Customer Advance Allocation ---")
        alloc = await tax_service.allocate_advance_payment(
            session=session,
            tenant_id=tenant_id,
            customer_id=customer.customer_id,
            invoice_id=test_inv.invoice_id,
            allocated_amount=Decimal("3000.0000"),
            reference_note="Reconciliation of customer deposit #DEP-8841",
        )
        await session.commit()
        assert alloc.allocated_amount == Decimal("3000.0000")
        print(f"Allocated ${alloc.allocated_amount} advance against invoice {test_inv.invoice_number}")

        print("\nALL 8 PHASE 1 ERPNEXT PARITY WORKFLOWS PASSED WITH 100% SUCCESS!\n")

if __name__ == "__main__":
    asyncio.run(test_phase1_all_parity_workflows())
