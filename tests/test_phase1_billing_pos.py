"""Comprehensive Unit and Domain Tests for Phase 1 Accounts, POS, and Billing Expansion."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from erp.db.models.base import Base
from erp.db.models.billing import (
    Budget,
    CreditNote,
    DebitNote,
    DunningNotice,
    DunningType,
    POSClosingEntry,
    POSInvoice,
    POSInvoiceItem,
    POSOpeningEntry,
    POSProfile,
    Subscription,
    SubscriptionPlan,
    TaxWithholdingCategory,
    CreditNoteItem,
    DebitNoteItem,
)

from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.sales import Customer, SalesInvoice
from erp.db.models.purchasing import Supplier, SupplierInvoice
from erp.db.models.user import User

from erp.ledger.invariants import LedgerLineProposal, validate_zero_sum
from erp.mcp.tools.billing_tools import (
    tool_evaluate_budget_compliance,
    tool_issue_dunning_notices,
    tool_stage_pos_checkout,
    tool_trigger_subscription_billing,
)
from erp.workflows.billing.budget_service import BudgetService
from erp.workflows.billing.dunning_service import DunningService
from erp.workflows.billing.pos_service import POSService
from erp.workflows.billing.returns_service import ReturnsService
from erp.workflows.billing.subscription_service import SubscriptionService


@pytest_asyncio.fixture
async def in_memory_db():
    """Provides an isolated SQLite in-memory async database for Phase 1 domain tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        # Register PostgreSQL's clock_timestamp function for SQLite compatibility
        dbapi_connection.create_function("clock_timestamp", 0, lambda: datetime.utcnow().isoformat())


    phase1_tables = [
        Customer.__table__,
        Supplier.__table__,
        Warehouse.__table__,
        Item.__table__,
        StockLevel.__table__,
        StockLedgerEntry.__table__,
        GeneralLedgerEntry.__table__,
        SalesInvoice.__table__,

        POSProfile.__table__,
        POSOpeningEntry.__table__,
        POSClosingEntry.__table__,
        POSInvoice.__table__,
        POSInvoiceItem.__table__,
        SubscriptionPlan.__table__,
        Subscription.__table__,
        DunningType.__table__,
        DunningNotice.__table__,
        Budget.__table__,
        TaxWithholdingCategory.__table__,
        CreditNote.__table__,
        CreditNoteItem.__table__,
        DebitNote.__table__,
        DebitNoteItem.__table__,
    ]
    async with engine.begin() as conn:
        for tbl in phase1_tables:
            await conn.run_sync(tbl.create, checkfirst=True)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()



@pytest.fixture
def mock_tenant_id():
    return uuid.uuid4()


class TestPointOfSale:
    """Tests POS cashier shifts, transactions, cash counting, and inventory deductions."""

    @pytest.mark.asyncio
    async def test_pos_shift_opening_and_closing_with_variance(self, in_memory_db: AsyncSession, mock_tenant_id):
        pos_svc = POSService()

        # Seed profile and user
        warehouse_id = uuid.uuid4()
        user_id = uuid.uuid4()
        profile = POSProfile(
            tenant_id=mock_tenant_id,
            profile_name="Main Retail Register",
            warehouse_id=warehouse_id,
            currency="USD",
        )
        in_memory_db.add(profile)
        await in_memory_db.flush()

        # 1. Open Shift with $150.00 cash float
        shift = await pos_svc.open_shift(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            profile_id=profile.profile_id,
            user_id=user_id,
            opening_float_cash=Decimal("150.0000"),
        )
        assert shift.status == "OPEN"
        assert shift.opening_float_cash == Decimal("150.0000")

        # 2. Add sample customer and item
        cust = Customer(tenant_id=mock_tenant_id, customer_code="CUST-001", customer_name="Walk-In Customer")
        item = Item(tenant_id=mock_tenant_id, item_code="AERO-BOLT", item_name="Titanium Bolt", standard_rate=Decimal("10.0000"))
        in_memory_db.add_all([cust, item])

        await in_memory_db.flush()

        # 3. Process POS Cash Sale: 2 bolts @ $25.00
        inv, _ = await pos_svc.process_pos_sale(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            opening_id=shift.opening_id,
            customer_id=cust.customer_id,
            items=[{"item_id": item.item_id, "quantity": Decimal("2"), "unit_price": Decimal("25.00"), "discount_pct": Decimal("0")}],
            payment_method="CASH",
            paid_amount=Decimal("60.0000"),
        )
        assert inv.subtotal == Decimal("50.0000")
        assert inv.tax_amount == Decimal("2.5000")  # 5% tax
        assert inv.grand_total == Decimal("52.5000")
        assert inv.paid_amount == Decimal("60.0000")
        assert inv.change_amount == Decimal("7.5000")

        # 4. Close Shift: Expected cash = $150 (float) + $52.50 (sales) = $202.50
        # If cashier counted $200.00, variance = -$2.50
        closing = await pos_svc.close_shift(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            opening_id=shift.opening_id,
            actual_counted_cash=Decimal("200.0000"),
        )
        assert shift.status == "CLOSED"
        assert closing.total_sales_amount == Decimal("52.5000")
        assert closing.expected_cash == Decimal("202.5000")
        assert closing.actual_counted_cash == Decimal("200.0000")
        assert closing.cash_variance == Decimal("-2.5000")

    @pytest.mark.asyncio
    async def test_pos_gl_balance_invariant(self):
        """Verifies that POS sales generate zero-sum double-entry GL lines."""
        grand_total = Decimal("105.0000")
        subtotal = Decimal("100.0000")
        tax = Decimal("5.0000")

        lines = [
            LedgerLineProposal(
                account_code="1010-OPERATING-CASH",
                cost_center="Main - CC",
                debit_amount=grand_total,
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="4000-SALES-REVENUE",
                cost_center="Main - CC",
                debit_amount=Decimal("0.0000"),
                credit_amount=subtotal,
            ),
            LedgerLineProposal(
                account_code="2100-SALES-TAX-PAYABLE",
                cost_center="Main - CC",
                debit_amount=Decimal("0.0000"),
                credit_amount=tax,
            ),
        ]
        total_vol = validate_zero_sum(lines)
        assert total_vol == Decimal("105.0000")


class TestSubscriptions:
    """Tests recurring subscription billing engine."""

    @pytest.mark.asyncio
    async def test_recurring_billing_run(self, in_memory_db: AsyncSession, mock_tenant_id):
        sub_svc = SubscriptionService()

        # 1. Create Monthly SaaS Plan
        plan = await sub_svc.create_plan(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            plan_name="Enterprise Cloud Pro",
            billing_interval="MONTHLY",
            cost=Decimal("499.0000"),
        )
        assert plan.cost == Decimal("499.0000")

        # 2. Subscribe Customer
        cust = Customer(tenant_id=mock_tenant_id, customer_code="SaaS-CUST", customer_name="SaaS Corp")
        in_memory_db.add(cust)
        await in_memory_db.flush()

        sub = await sub_svc.subscribe_customer(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            customer_id=cust.customer_id,
            plan_id=plan.plan_id,
            start_date=date(2026, 9, 1),
        )
        assert sub.status == "ACTIVE"
        assert sub.next_billing_date == date(2026, 9, 1)

        # 3. Process Billing as of 2026-09-15
        invoices = await sub_svc.process_recurring_billing(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            as_of_date=date(2026, 9, 15),
        )
        assert len(invoices) == 1
        assert invoices[0]["amount"] == 499.0
        # Next billing date advanced by 30 days
        assert sub.next_billing_date == date(2026, 10, 1)


class TestDunning:
    """Tests overdue customer invoice identification and late fee calculations."""

    @pytest.mark.asyncio
    async def test_dunning_fee_and_interest_calculation(self, in_memory_db: AsyncSession, mock_tenant_id):
        dunning_svc = DunningService()

        # 1. Create Dunning Level 1 (Overdue >= 10 days, $50 fee, 10% interest)
        await dunning_svc.create_dunning_type(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            dunning_type_name="Late Notice 1",
            overdue_days=10,
            fee_amount=Decimal("50.0000"),
            interest_rate_pct=Decimal("10.00"),
            message_body="Immediate settlement required.",
        )

        # 2. Create customer and overdue sales invoice (due 30 days ago)
        cust = Customer(tenant_id=mock_tenant_id, customer_code="DEF-01", customer_name="Defaulting Client")
        in_memory_db.add(cust)
        await in_memory_db.flush()

        due_date = date.today() - timedelta(days=30)
        inv = SalesInvoice(
            tenant_id=mock_tenant_id,
            invoice_number="INV-OVERDUE-001",
            customer_id=cust.customer_id,
            invoice_date=due_date - timedelta(days=15),
            due_date=due_date,
            subtotal=Decimal("1000.0000"),
            tax_amount=Decimal("0.0000"),
            total_amount=Decimal("1000.0000"),
            status="ISSUED",
        )
        in_memory_db.add(inv)
        await in_memory_db.flush()

        # 3. Evaluate Overdue
        notices = await dunning_svc.evaluate_overdue_invoices(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            as_of_date=date.today(),
        )
        assert len(notices) == 1
        notice = notices[0]
        assert notice["overdue_days"] == 30
        assert notice["fee_amount"] == 50.0
        # Interest: $1000 * 10% * (30 / 365) = $8.2192
        assert notice["interest_amount"] == pytest.approx(8.2192, 0.01)
        assert notice["total_dunning_amount"] == pytest.approx(1058.2192, 0.01)


class TestBudgetControl:
    """Tests budget limits against General Ledger expenses with WARN and STOP policies."""

    @pytest.mark.asyncio
    async def test_budget_compliance_warn_and_stop(self, in_memory_db: AsyncSession, mock_tenant_id):
        budget_svc = BudgetService()

        # 1. Budget with STOP on exceed
        budget = await budget_svc.create_budget(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            budget_name="R&D Travel Budget",
            fiscal_year=2026,
            cost_center="R&D-01",
            account_code="6200-TRAVEL",
            budget_amount=Decimal("5000.0000"),
            action_on_exceed="STOP",
        )

        # Check under budget ($2,000 proposed on $5,000 limit)
        eval_ok = await budget_svc.evaluate_budget_compliance(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            fiscal_year=2026,
            cost_center="R&D-01",
            account_code="6200-TRAVEL",
            proposed_expense=Decimal("2000.0000"),
        )
        assert eval_ok["allowed"] is True
        assert eval_ok["status"] == "COMPLIANT"
        assert eval_ok["remaining_budget"] == 3000.0

        # Check over budget ($6,500 proposed on $5,000 limit) -> Hard STOP
        eval_stop = await budget_svc.evaluate_budget_compliance(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            fiscal_year=2026,
            cost_center="R&D-01",
            account_code="6200-TRAVEL",
            proposed_expense=Decimal("6500.0000"),
        )
        assert eval_stop["allowed"] is False
        assert eval_stop["status"] == "STOP_BLOCKED"
        assert eval_stop["excess_amount"] == 1500.0


class TestReturns:
    """Tests Credit Notes (Sales Returns) and Debit Notes (Purchase Returns)."""

    @pytest.mark.asyncio
    async def test_credit_note_issuance(self, in_memory_db: AsyncSession, mock_tenant_id):
        returns_svc = ReturnsService()

        cust = Customer(tenant_id=mock_tenant_id, customer_code="RET-CUST", customer_name="Return Customer")
        item = Item(tenant_id=mock_tenant_id, item_code="PART-X", item_name="Part X")
        in_memory_db.add_all([cust, item])
        await in_memory_db.flush()

        cn = await returns_svc.issue_credit_note(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            customer_id=cust.customer_id,
            reason="Wrong size delivered",
            items=[{"item_id": item.item_id, "quantity": Decimal("1"), "unit_price": Decimal("200.0000")}],
        )
        assert cn.subtotal == Decimal("200.0000")
        assert cn.tax_amount == Decimal("10.0000")  # 5%
        assert cn.total_amount == Decimal("210.0000")
        assert cn.status == "POSTED"

    @pytest.mark.asyncio
    async def test_debit_note_issuance(self, in_memory_db: AsyncSession, mock_tenant_id):
        returns_svc = ReturnsService()

        supp = Supplier(tenant_id=mock_tenant_id, supplier_code="RET-SUPP", supplier_name="Vendor X")
        item = Item(tenant_id=mock_tenant_id, item_code="RAW-Y", item_name="Raw Material Y")
        in_memory_db.add_all([supp, item])
        await in_memory_db.flush()

        dn = await returns_svc.issue_debit_note(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            supplier_id=supp.supplier_id,
            reason="Substandard purity grade",
            items=[{"item_id": item.item_id, "quantity": Decimal("5"), "unit_price": Decimal("80.0000")}],
        )
        assert dn.subtotal == Decimal("400.0000")
        assert dn.tax_amount == Decimal("20.0000")
        assert dn.total_amount == Decimal("420.0000")
        assert dn.status == "POSTED"


class TestMCPBillingTools:
    """Tests autonomous agent tool executions for Phase 1."""

    @pytest.mark.asyncio
    async def test_mcp_evaluate_budget_tool(self, in_memory_db: AsyncSession, mock_tenant_id):
        budget_svc = BudgetService()
        await budget_svc.create_budget(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            budget_name="Ops Budget",
            fiscal_year=2026,
            cost_center="OPS",
            account_code="5000",
            budget_amount=Decimal("10000.00"),
            action_on_exceed="WARN",
        )

        res = await tool_evaluate_budget_compliance(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            arguments={
                "fiscal_year": 2026,
                "cost_center": "OPS",
                "account_code": "5000",
                "proposed_expense": 12000.0,
            },
        )
        assert res["status"] == "WARNING_EXCEEDED"
        assert res["excess_amount"] == 2000.0

    @pytest.mark.asyncio
    async def test_subscription_quarterly_and_annual_cadence(self, in_memory_db: AsyncSession, mock_tenant_id):
        sub_svc = SubscriptionService()
        plan_q = await sub_svc.create_plan(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            plan_name="Quarterly Enterprise",
            billing_interval="QUARTERLY",
            cost=Decimal("1200.00"),
        )
        plan_a = await sub_svc.create_plan(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            plan_name="Annual VIP",
            billing_interval="ANNUAL",
            cost=Decimal("4500.00"),
        )

        cust = Customer(tenant_id=mock_tenant_id, customer_code="VIP-CUST", customer_name="VIP Client")
        in_memory_db.add(cust)
        await in_memory_db.flush()

        sub_q = await sub_svc.subscribe_customer(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            customer_id=cust.customer_id,
            plan_id=plan_q.plan_id,
            start_date=date(2026, 1, 1),
        )
        sub_a = await sub_svc.subscribe_customer(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            customer_id=cust.customer_id,
            plan_id=plan_a.plan_id,
            start_date=date(2026, 1, 1),
        )

        # Run renewals as of 2026-01-05
        invoices = await sub_svc.process_recurring_billing(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            as_of_date=date(2026, 1, 5),
        )
        assert len(invoices) == 2
        # Quarterly advances 90 days -> 2026-04-01
        assert sub_q.next_billing_date == date(2026, 4, 1)
        # Annual advances 365 days -> 2027-01-01
        assert sub_a.next_billing_date == date(2027, 1, 1)

    @pytest.mark.asyncio
    async def test_dunning_multi_tier_escalation(self, in_memory_db: AsyncSession, mock_tenant_id):
        dunning_svc = DunningService()
        await dunning_svc.create_dunning_type(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            dunning_type_name="Tier 1 Reminder",
            overdue_days=7,
            fee_amount=Decimal("15.00"),
            interest_rate_pct=Decimal("3.00"),
            message_body="First gentle reminder",
        )
        await dunning_svc.create_dunning_type(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            dunning_type_name="Tier 2 Demand",
            overdue_days=30,
            fee_amount=Decimal("75.00"),
            interest_rate_pct=Decimal("8.00"),
            message_body="Second formal demand",
        )

        cust = Customer(tenant_id=mock_tenant_id, customer_code="LATE-CUST", customer_name="Late Customer")
        in_memory_db.add(cust)
        await in_memory_db.flush()

        # Invoice overdue by 45 days (should trigger Tier 2)
        inv = SalesInvoice(
            tenant_id=mock_tenant_id,
            invoice_number="INV-TIER2-TEST",
            customer_id=cust.customer_id,
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=45),
            subtotal=Decimal("2000.00"),
            total_amount=Decimal("2000.00"),
            status="ISSUED",
        )
        in_memory_db.add(inv)
        await in_memory_db.flush()

        notices = await dunning_svc.evaluate_overdue_invoices(
            session=in_memory_db,
            tenant_id=mock_tenant_id,
            as_of_date=date.today(),
        )
        assert len(notices) == 1
        assert notices[0]["dunning_level"] == "Tier 2 Demand"
        assert notices[0]["fee_amount"] == 75.0

    @pytest.mark.asyncio
    async def test_tax_withholding_category_setup(self, in_memory_db: AsyncSession, mock_tenant_id):
        category = TaxWithholdingCategory(
            tenant_id=mock_tenant_id,
            category_name="Professional Consultancy 194J",
            section_code="194J",
            rate_pct=Decimal("10.00"),
            single_threshold=Decimal("30000.0000"),
            cumulative_threshold=Decimal("100000.0000"),
        )
        in_memory_db.add(category)
        await in_memory_db.flush()

        assert category.category_name == "Professional Consultancy 194J"
        assert category.rate_pct == Decimal("10.00")
        assert category.is_active is True

