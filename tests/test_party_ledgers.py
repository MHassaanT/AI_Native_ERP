"""Real PostgreSQL acceptance for F01/F02; only an explicit disposable DB is used."""
from datetime import date
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import func, inspect as sa_inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import erp.db.models
from erp.db.models.base import Base
from erp.db.models.billing import CreditNote, CreditNoteItem, POSInvoice, POSInvoiceItem, POSOpeningEntry, POSProfile
from erp.db.models.inventory import Item, StockLevel
from erp.db.models.ledger import Account, CostCenter
from erp.db.models.projects import Project
from erp.db.models.ledger import GeneralLedgerEntry as GL
from erp.db.models.purchasing import MaterialRequest, PurchaseOrder, PurchaseOrderItem, Supplier, SupplierInvoice, SupplierQuotationItem
from erp.db.models.shared_master import ItemPrice, PriceList, ProductBundle, ProductBundleItem, UOM, UOMConversion
from erp.db.models.inventory import Warehouse
from erp.db.models.sales import Customer, DeliveryNoteItem, SalesInvoice, SalesInvoiceItem, SalesOrder, SalesOrderItem, SalesQuotation, SalesQuotationItem
from erp.db.models.tenant import Tenant
from erp.db.models.user import User
from erp.db.models.onboarding import TenantSettings
from erp.ledger.engine import LedgerEngine, TransactionProposal
from erp.ledger.invariants import LedgerLineProposal
from erp.workflows.reports.party_ledger_service import party_ledger_service
from erp.workflows.reconciliation.semantic_matcher import SemanticReconciler
from erp.workflows.reconciliation.auto_clear import AutoClearingEngine, bank_transaction_source_id
from erp.workflows.reconciliation.bank_feed_ingestor import RawBankTransaction
from erp.workflows.reports.enterprise_reports_service import enterprise_reports_service
from erp.workflows.procurement.requisition_service import requisition_service
from erp.workflows.procurement.sourcing_service import sourcing_service
from erp.workflows.billing.returns_service import ReturnsService
from erp.workflows.billing.pos_service import POSService
from erp.workflows.billing.tax_and_terms_service import TaxAndTermsService
from erp.workflows.commercial.bundle_service import bundle_delivery_snapshot, bundle_stock_requirements, snapshot_bundle_components
_api_package = ModuleType("erp.api")
_api_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src/erp/api")]
_routes_package = ModuleType("erp.api.routes")
_routes_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src/erp/api/routes")]
sys.modules.setdefault("erp.api", _api_package)
sys.modules.setdefault("erp.api.routes", _routes_package)
from erp.api.routes.commercial import (CreateSalesInvoiceRequest, CreateSalesQuoteRequest,
    ConvertQuoteToOrderRequest, FulfillOrderItemRequest, FulfillOrderRequest, QuoteItemSpec,
    SalesQuoteLineSpec, cancel_sales_order, convert_quote_to_order, create_sales_invoice_from_delivery,
    create_sales_quote, fulfill_sales_order, list_delivery_notes, sales_order_timeline)
sys.modules.pop("erp.api.routes", None)
sys.modules.pop("erp.api", None)


@pytest_asyncio.fixture
async def party_db():
    url = os.environ.get("PARITY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PARITY_TEST_DATABASE_URL to a disposable PostgreSQL parity_* database.")
    if not (make_url(url).database or "").startswith("parity_"):
        pytest.fail("Party acceptance tests require an explicitly named parity_* disposable database.")
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        schema = "test_party_" + uuid.uuid4().hex
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        # Exercise the real application tables and their FK dependencies. Do not
        # let unrelated HR/WhatsApp schema defects hide ledger test results.
        names = {"general_ledger_entries", "chart_of_accounts", "customers", "suppliers", "sales_invoices",
                 "supplier_invoices", "credit_notes", "debit_notes", "debit_note_items", "agent_audit_logs",
                 "transactional_outbox", "fiscal_periods", "advance_payment_allocations", "delivery_note_items", "sales_invoice_items",
                 "credit_note_items", "stock_ledger_entries", "items", "sales_orders", "sales_order_items",
                 "material_requests", "material_request_items", "purchase_orders", "purchase_order_items",
                 "supplier_quotations", "supplier_quotation_items", "request_for_quotations", "rfq_items",
                 "sales_quotations", "sales_quotation_items", "product_bundles", "product_bundle_items",
                 "sales_partners", "sales_teams", "pos_invoices", "pos_invoice_items", "pos_invoice_payments", "pos_profiles", "pos_opening_entries",
                 "tenant_settings", "price_lists", "item_prices", "pricing_rules", "promotional_schemes",
                 "uoms", "uom_conversions", "projects", "cost_centers", "warehouses", "stock_levels", "document_audit_batches",
                 "work_orders"}
        tables = {Base.metadata.tables[name] for name in names}
        pending = list(tables)
        while pending:
            table = pending.pop()
            for key in table.foreign_keys:
                if key.column.table not in tables:
                    tables.add(key.column.table)
                    pending.append(key.column.table)
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=list(tables)))
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


async def _party(db, tenant, kind):
    if kind == "CUSTOMER":
        row = Customer(tenant_id=tenant, customer_code=uuid.uuid4().hex, customer_name="Customer at posting")
    else:
        row = Supplier(tenant_id=tenant, supplier_code=uuid.uuid4().hex, supplier_name="Supplier at posting")
    db.add(row)
    await db.flush()
    return row


async def _post(db, tenant, kind, party_id, amount, day, *, currency="USD", invoice_id=None, source="MANUAL_JOURNAL"):
    """amount is an increase in receivable/payable, negative is a settlement."""
    amount = Decimal(str(amount))
    debit = amount if kind == "CUSTOMER" else -amount
    control = LedgerLineProposal(
        account_code="1200-AR-CUSTOMERS" if kind == "CUSTOMER" else "2100-AP-VENDORS",
        cost_center="TEST", currency=currency,
        debit_amount=max(debit, Decimal(0)), credit_amount=max(-debit, Decimal(0)),
        party_type=kind, party_id=party_id,
        against_document_type=("SALES_INVOICE" if kind == "CUSTOMER" else "SUPPLIER_INVOICE") if invoice_id else None,
        against_document_id=invoice_id,
    )
    counterpart = LedgerLineProposal(
        account_code="1020-BANK-OPERATING", cost_center="TEST", currency=currency,
        debit_amount=control.credit_amount, credit_amount=control.debit_amount,
    )
    return await LedgerEngine(validate_masters=False).commit_transaction(db, TransactionProposal(
        tenant_id=tenant, posting_date=day, currency=currency, source_document_type=source,
        source_document_id=invoice_id or uuid.uuid4(), entries=[control, counterpart],
        human_in_the_loop_approved=True,
    ))


@pytest.mark.asyncio
async def test_customer_running_balance_opening_pagination_and_snapshot(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 100, date(2025, 12, 31))
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 200, date(2026, 1, 1))
    await _post(db, tenant, "CUSTOMER", customer.customer_id, -60, date(2026, 1, 2))
    await _post(db, tenant, "CUSTOMER", customer.customer_id, -20, date(2026, 1, 3), source="CREDIT_NOTE")
    customer.customer_name = "Renamed later"
    await db.flush()
    journal = await party_ledger_service.journal(db, tenant, "CUSTOMER", customer.customer_id,
        date(2026, 1, 1), date(2026, 1, 31), limit=1, offset=1)
    assert journal["total_rows"] == 3
    assert journal["totals_by_currency"] == [{"currency": "USD", "opening_balance": Decimal(100),
        "debit": Decimal(200), "credit": Decimal(80), "closing_balance": Decimal(220)}]
    assert journal["rows"][0]["running_balance"] == Decimal(240)
    assert journal["rows"][0]["party_name_snapshot"] == "Customer at posting"
    assert journal["rows"][0]["source_url"].startswith("/ledger?transaction_id=")
    assert await db.scalar(select(func.count()).select_from(GL).where(GL.party_id == customer.customer_id)) == 4
    assert await db.scalar(select(func.count()).select_from(GL).where(GL.party_id.is_(None))) == 4


@pytest.mark.asyncio
async def test_matched_supplier_invoice_remains_payable_until_real_settlements(party_db):
    db, tenant = party_db, uuid.uuid4()
    supplier = await _party(db, tenant, "SUPPLIER")
    invoice = SupplierInvoice(tenant_id=tenant, supplier_id=supplier.supplier_id, invoice_number="S-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 10), currency="USD", subtotal=150,
        tax_amount=0, total_amount=150, matching_status="MATCHED")
    db.add(invoice)
    await db.flush()
    await _post(db, tenant, "SUPPLIER", supplier.supplier_id, 150, date(2026, 1, 1),
        source="AUTOMATED_AP_MATCH", invoice_id=invoice.invoice_id)
    summary = await party_ledger_service.summary(db, tenant, "SUPPLIER", date(2026, 1, 1), date(2026, 1, 31))
    assert summary[0]["open_balance"] == 150
    assert summary[0]["settled_or_posted"] == 0
    await _post(db, tenant, "SUPPLIER", supplier.supplier_id, -40, date(2026, 1, 2), invoice_id=invoice.invoice_id)
    await _post(db, tenant, "SUPPLIER", supplier.supplier_id, -15, date(2026, 1, 3), source="DEBIT_NOTE", invoice_id=invoice.invoice_id)
    journal = await party_ledger_service.journal(db, tenant, "SUPPLIER", supplier.supplier_id,
        date(2026, 1, 1), date(2026, 1, 31))
    assert [row["running_balance"] for row in journal["rows"]] == [150, 110, 95]
    assert journal["outstanding_invoices"][0]["outstanding"] == 95
    assert journal["outstanding_invoices"][0]["overdue_days"] == 21


@pytest.mark.asyncio
async def test_supplier_debit_note_reduces_the_same_ap_control_balance(party_db):
    db, tenant = party_db, uuid.uuid4()
    supplier = await _party(db, tenant, "SUPPLIER")
    item = Item(tenant_id=tenant, item_code=uuid.uuid4().hex, item_name="Returned stock", standard_rate=100)
    invoice = SupplierInvoice(tenant_id=tenant, supplier_id=supplier.supplier_id, invoice_number="S-DN-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 30), currency="USD", subtotal=100,
        tax_amount=0, total_amount=100, matching_status="MATCHED")
    db.add_all([item, invoice])
    await db.flush()
    await _post(db, tenant, "SUPPLIER", supplier.supplier_id, 100, date(2026, 1, 1),
        currency="USD", invoice_id=invoice.invoice_id, source="SUPPLIER_INVOICE")

    debit_note = await ReturnsService().issue_debit_note(db, tenant, supplier.supplier_id,
        "Damaged goods", [{"item_id": item.item_id, "quantity": Decimal("1"), "unit_price": Decimal("20")}],
        supplier_invoice_id=invoice.invoice_id)
    note_leg = (await db.execute(select(GL).where(
        GL.source_document_type == "DEBIT_NOTE", GL.source_document_id == debit_note.debit_note_id,
        GL.party_id == supplier.supplier_id,
    ))).scalar_one()
    assert note_leg.account_code == "2100-AP-VENDORS"
    assert note_leg.against_document_id == invoice.invoice_id
    ap_balance = await db.scalar(select(func.sum(GL.credit_amount - GL.debit_amount)).where(
        GL.tenant_id == tenant, GL.account_code == "2100-AP-VENDORS", GL.party_id == supplier.supplier_id,
    ))
    assert ap_balance == Decimal("79.0000")
    journal = await party_ledger_service.journal(db, tenant, "SUPPLIER", supplier.supplier_id,
        date(2026, 1, 1), date(2026, 12, 31))
    assert journal["outstanding_invoices"][0]["outstanding"] == Decimal("79.0000")


@pytest.mark.asyncio
async def test_advance_allocation_transfers_only_posted_customer_deposit_to_ar(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="C-ADV-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 31), currency="USD", subtotal=100,
        tax_amount=0, total_amount=100, status="ISSUED")
    db.add(invoice)
    await db.flush()
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 100, date(2026, 1, 1),
        invoice_id=invoice.invoice_id, source="SALES_INVOICE")
    await LedgerEngine(validate_masters=False).commit_transaction(db, TransactionProposal(
        tenant_id=tenant, posting_date=date(2026, 1, 2), currency="USD",
        source_document_type="CUSTOMER_ADVANCE_RECEIPT", source_document_id=uuid.uuid4(),
        entries=[
            LedgerLineProposal(account_code="1020-BANK-OPERATING", cost_center="TEST",
                debit_amount=40, credit_amount=0, currency="USD"),
            LedgerLineProposal(account_code="2150-CUSTOMER-ADVANCES", cost_center="TEST",
                debit_amount=0, credit_amount=40, currency="USD",
                party_type="CUSTOMER", party_id=customer.customer_id),
        ], human_in_the_loop_approved=True,
    ))

    allocation = await TaxAndTermsService().allocate_advance_payment(
        db, tenant, customer.customer_id, invoice.invoice_id, Decimal("25"), "deposit 40; apply 25",
    )
    assert allocation.allocated_amount == Decimal("25")
    assert allocation.ledger_posted is True
    assert invoice.status == "ISSUED"
    advance_remaining = await db.scalar(select(func.sum(GL.credit_amount - GL.debit_amount)).where(
        GL.tenant_id == tenant, GL.account_code == "2150-CUSTOMER-ADVANCES",
        GL.party_id == customer.customer_id,
    ))
    assert advance_remaining == Decimal("15.0000")
    journal = await party_ledger_service.journal(db, tenant, "CUSTOMER", customer.customer_id,
        date(2026, 1, 1), date(2026, 12, 31))
    assert journal["outstanding_invoices"][0]["outstanding"] == Decimal("75.0000")
    assert journal["totals_by_currency"][0]["closing_balance"] == Decimal("60.0000")
    with pytest.raises(ValueError, match="exceeds available customer advance"):
        await TaxAndTermsService().allocate_advance_payment(
            db, tenant, customer.customer_id, invoice.invoice_id, Decimal("16"),
        )


@pytest.mark.asyncio
async def test_advance_allocation_cannot_invent_a_deposit_or_settle_unposted_invoice(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="C-ADV-2",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 31), currency="USD", subtotal=100,
        tax_amount=0, total_amount=100, status="ISSUED")
    db.add(invoice)
    await db.flush()
    with pytest.raises(ValueError, match="posted, outstanding receivable"):
        await TaxAndTermsService().allocate_advance_payment(
            db, tenant, customer.customer_id, invoice.invoice_id, Decimal("10"),
        )
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 100, date(2026, 1, 1),
        invoice_id=invoice.invoice_id, source="SALES_INVOICE")
    with pytest.raises(ValueError, match="No posted customer advance"):
        await TaxAndTermsService().allocate_advance_payment(
            db, tenant, customer.customer_id, invoice.invoice_id, Decimal("10"),
        )


@pytest.mark.asyncio
async def test_currency_and_tenant_balances_are_never_combined(party_db):
    db, tenant, other = party_db, uuid.uuid4(), uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    outsider = await _party(db, other, "CUSTOMER")
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 20, date(2026, 1, 1), currency="USD")
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 30, date(2026, 1, 1), currency="EUR")
    await _post(db, other, "CUSTOMER", outsider.customer_id, 900, date(2026, 1, 1))
    journal = await party_ledger_service.journal(db, tenant, "CUSTOMER", customer.customer_id,
        date(2026, 1, 1), date(2026, 1, 31))
    assert {row["currency"]: row["closing_balance"] for row in journal["totals_by_currency"]} == {"EUR": 30, "USD": 20}
    assert {row["currency"]: row["running_balance"] for row in journal["rows"]} == {"EUR": 30, "USD": 20}
    with pytest.raises(LookupError):
        await party_ledger_service.journal(db, tenant, "CUSTOMER", outsider.customer_id)
    with pytest.raises(ValueError, match="workspace"):
        await _post(db, tenant, "CUSTOMER", outsider.customer_id, 1, date(2026, 1, 1))
    assert await db.scalar(select(func.count()).select_from(GL).where(GL.tenant_id == tenant)) == 4


@pytest.mark.asyncio
async def test_settlement_must_reference_same_party_and_currency(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer, other = await _party(db, tenant, "CUSTOMER"), await _party(db, tenant, "CUSTOMER")
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="C-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 15), currency="USD", subtotal=100, tax_amount=0, total_amount=100)
    db.add(invoice)
    await db.flush()
    for party_id, currency in ((other.customer_id, "USD"), (customer.customer_id, "EUR")):
        with pytest.raises(ValueError, match="same workspace, party and currency"):
            await _post(db, tenant, "CUSTOMER", party_id, -20, date(2026, 1, 2), currency=currency, invoice_id=invoice.invoice_id)
    assert await db.scalar(select(func.count()).select_from(GL)) == 0


@pytest.mark.asyncio
async def test_bank_matcher_only_matches_open_posted_invoice_balances(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    order = SalesOrder(tenant_id=tenant, customer_id=customer.customer_id, order_number="SO-100",
        order_date=date(2026, 1, 1), delivery_date=date(2026, 1, 2), total_amount=100,
        status="DELIVERED")
    db.add(order)
    await db.flush()
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, order_id=order.order_id,
        invoice_number="SI-100", invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 31),
        currency="USD", subtotal=100, tax_amount=0, total_amount=100, status="ISSUED")
    db.add(invoice)
    await db.flush()
    await _post(db, tenant, "CUSTOMER", customer.customer_id, 100, date(2026, 1, 1),
        currency="USD", invoice_id=invoice.invoice_id, source="SALES_INVOICE")

    matcher = SemanticReconciler()
    initial = await matcher.find_matching_receivable(db, tenant, Decimal("100"), customer.customer_name,
        "SI-100", currency="USD")
    assert initial.meets_auto_clear_threshold
    assert [candidate.order_id for candidate in initial.candidates] == [invoice.invoice_id]
    assert initial.best_match.order_amount == Decimal("100.0000")

    await _post(db, tenant, "CUSTOMER", customer.customer_id, -40, date(2026, 1, 2),
        currency="USD", invoice_id=invoice.invoice_id, source="CUSTOMER_PAYMENT")
    overpayment = await matcher.find_matching_receivable(db, tenant, Decimal("100"), customer.customer_name,
        "SI-100", currency="USD")
    wrong_currency = await matcher.find_matching_receivable(db, tenant, Decimal("60"), customer.customer_name,
        "SI-100", currency="EUR")
    remaining = await matcher.find_matching_receivable(db, tenant, Decimal("60"), customer.customer_name,
        "SI-100", currency="USD")
    assert overpayment.best_match is None
    assert wrong_currency.best_match is None
    assert remaining.best_match.order_amount == Decimal("60.0000")


@pytest.mark.asyncio
async def test_bank_feed_retries_are_idempotent_and_conflicting_reuse_is_staged(party_db, monkeypatch):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="SI-RETRY",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 31), currency="USD",
        subtotal=75, tax_amount=0, total_amount=75, status="ISSUED")
    db.add(invoice)
    await db.flush()
    tx = RawBankTransaction(transaction_id="provider-settlement-123", account_number="BANK-1",
        booking_date=date(2026, 1, 2), value_date=date(2026, 1, 2), amount=Decimal("75"),
        currency="USD", counterparty_name=customer.customer_name, remittance_information="SI-RETRY")
    source_id, ledger_id = bank_transaction_source_id(tenant, tx), uuid.uuid4()
    db.add_all([
        GL(tenant_id=tenant, transaction_id=ledger_id, posting_date=tx.booking_date,
            fiscal_year=2026, fiscal_period=1, account_code="1020-BANK-OPERATING", cost_center="TEST",
            debit_amount=75, credit_amount=0, currency="USD", exchange_rate=1,
            source_document_type="AUTO_BANK_RECONCILIATION", source_document_id=source_id),
        GL(tenant_id=tenant, transaction_id=ledger_id, posting_date=tx.booking_date,
            fiscal_year=2026, fiscal_period=1, account_code="1200-AR-CUSTOMERS", cost_center="TEST",
            debit_amount=0, credit_amount=75, currency="USD", exchange_rate=1,
            source_document_type="AUTO_BANK_RECONCILIATION", source_document_id=source_id,
            party_type="CUSTOMER", party_id=customer.customer_id, party_name_snapshot=customer.customer_name,
            against_document_type="SALES_INVOICE", against_document_id=invoice.invoice_id),
    ])
    await db.flush()

    async def should_not_rematch(**kwargs):
        raise AssertionError("A previously posted bank transaction must not be rematched.")

    monkeypatch.setattr("erp.workflows.reconciliation.auto_clear.semantic_reconciler.find_matching_receivable", should_not_rematch)
    engine = AutoClearingEngine()
    duplicate = await engine.process_bank_transaction(db, tenant, tx)
    assert duplicate.is_auto_cleared
    assert duplicate.ledger_transaction_id == ledger_id
    assert duplicate.matched_order_number == "SI-RETRY"

    conflicting = tx.model_copy(update={"amount": Decimal("76")})
    rejected = await engine.process_bank_transaction(db, tenant, conflicting)
    assert not rejected.is_auto_cleared
    assert rejected.reconciliation_worklist_item["status"] == "IDEMPOTENCY_KEY_CONFLICT"


@pytest.mark.asyncio
async def test_047_backfill_attributes_only_documented_source_control_legs(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="LEGACY-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 15), currency="USD", subtotal=100, tax_amount=0, total_amount=100)
    db.add(invoice)
    await db.flush()
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/047_party_ledger_dimensions.py"
    spec = importlib.util.spec_from_file_location("migration_047", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    for account, debit, credit, source_id in (
        ("1200-AR-CUSTOMERS", 100, 0, invoice.invoice_id),
        ("4000-SALES-REVENUE", 0, 100, invoice.invoice_id),
        ("1200-AR-CUSTOMERS", 25, 0, uuid.uuid4()),
    ):
        await db.execute(text("""INSERT INTO general_ledger_entries
            (entry_id,tenant_id,transaction_id,posting_date,fiscal_year,fiscal_period,account_code,cost_center,
             debit_amount,credit_amount,currency,exchange_rate,source_document_type,source_document_id,period_closing_locked)
            VALUES (:id,:tenant,:tx,'2026-01-01',2026,1,:account,'TEST',:debit,:credit,'USD',1,'SALES_INVOICE',:source,false)
        """), {"id": uuid.uuid4(), "tenant": tenant, "tx": uuid.uuid4(), "account": account,
               "debit": debit, "credit": credit, "source": source_id})
    await connection.run_sync(run_migration, migration.upgrade)
    rows = (await db.execute(select(GL).order_by(GL.debit_amount.desc()))).scalars().all()
    assert rows[0].party_id == customer.customer_id
    assert rows[0].against_document_id == invoice.invoice_id
    assert rows[1].party_id is None and rows[2].party_id is None
    unlinked = await party_ledger_service.unattributed(db, tenant, date(2026, 1, 31))
    assert unlinked["total_rows"] == 1
    assert unlinked["rows"][0]["debit"] == 25
    assert unlinked["rows"][0]["attribution"] == "UNATTRIBUTED"


@pytest.mark.asyncio
async def test_048_cost_snapshot_migration_executes_on_sales_tables(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/048_sales_cost_snapshots.py"
    spec = importlib.util.spec_from_file_location("migration_048", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_gross_profit_uses_frozen_cost_and_reverses_linked_return(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    item = Item(tenant_id=tenant, item_code=uuid.uuid4().hex, item_name="Historical-cost item",
                stock_uom="EA", standard_rate=Decimal("9999"))
    invoice = SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="GP-1",
        invoice_date=date(2026, 1, 1), due_date=date(2026, 1, 31), currency="USD",
        subtotal=100, tax_amount=0, total_amount=100, status="ISSUED")
    db.add_all([item, invoice])
    await db.flush()
    invoice_line = SalesInvoiceItem(
        tenant_id=tenant, invoice_id=invoice.invoice_id, item_id=item.item_id,
        quantity=2, unit_price=50, line_total=100,
        stock_quantity=4, cost_unit_stock=10, cost_amount=40,
        cost_valuation_method="STOCK_LEVEL", cost_source="DELIVERY_STOCK_LEVEL",
        cost_is_estimated=False,
    )
    db.add(invoice_line)
    await db.flush()
    credit = CreditNote(tenant_id=tenant, credit_note_number="GP-CR-1", invoice_id=invoice.invoice_id,
        customer_id=customer.customer_id, posting_date=date(2026, 1, 15), reason="Return",
        currency="USD", subtotal=50, tax_amount=0, total_amount=50, status="POSTED")
    db.add(credit)
    await db.flush()
    db.add(CreditNoteItem(tenant_id=tenant, credit_note_id=credit.credit_note_id,
        item_id=item.item_id, sales_invoice_item_id=invoice_line.invoice_item_id,
        quantity=1, unit_price=50, line_total=50,
        stock_quantity=2, cost_unit_stock=10, cost_amount=20,
        cost_valuation_method="STOCK_LEVEL", cost_source="DELIVERY_STOCK_LEVEL",
        cost_is_estimated=False))
    await db.flush()
    report = await enterprise_reports_service.run("gross-profit-analysis", db, tenant,
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))
    row = report["rows"][0]
    assert row["revenue"] == Decimal("50.0000")
    assert row["recorded_cost"] == Decimal("20.0000")
    assert row["estimated_cost"] == 0
    assert row["gross_profit"] == Decimal("30.0000")
    assert row["cost_snapshot_complete"] is True


@pytest.mark.asyncio
async def test_gross_profit_includes_pos_sales_and_source_costed_returns(party_db):
    db = party_db
    tenant_row = Tenant(tenant_slug=uuid.uuid4().hex, company_name="POS gross-profit tenant", currency="USD")
    db.add(tenant_row)
    await db.flush()
    tenant = tenant_row.tenant_id
    customer = await _party(db, tenant, "CUSTOMER")
    item = Item(tenant_id=tenant, item_code=uuid.uuid4().hex, item_name="POS margin item",
                stock_uom="EA", standard_rate=Decimal("9999"))
    user = User(tenant_id=tenant, email=f"{uuid.uuid4().hex}@example.test",
                hashed_password="test", full_name="POS Clerk")
    warehouse = Warehouse(tenant_id=tenant, warehouse_code=uuid.uuid4().hex[:12], warehouse_name="POS warehouse")
    db.add_all([item, user, warehouse])
    await db.flush()
    profile = POSProfile(tenant_id=tenant, profile_name="POS report profile",
                         warehouse_id=warehouse.warehouse_id, currency="USD")
    db.add(profile)
    await db.flush()
    opening = POSOpeningEntry(tenant_id=tenant, profile_id=profile.profile_id, user_id=user.user_id)
    db.add(opening)
    await db.flush()
    sale = POSInvoice(tenant_id=tenant, pos_invoice_number="POS-GP-1", opening_id=opening.opening_id,
        customer_id=customer.customer_id, posting_date=date(2026, 1, 5), subtotal=100, tax_amount=0,
        discount_amount=0, grand_total=100, paid_amount=100, status="PAID", is_return=False)
    db.add(sale)
    await db.flush()
    source_line = POSInvoiceItem(tenant_id=tenant, pos_invoice_id=sale.pos_invoice_id,
        item_id=item.item_id, quantity=4, unit_price=25, discount_pct=0, line_total=100,
        stock_quantity=4, cost_unit_stock=10, cost_amount=40, cost_valuation_method="STOCK_LEVEL",
        cost_source="POS_STOCK_LEVEL", cost_is_estimated=False)
    db.add(source_line)
    await db.flush()
    returned = POSInvoice(tenant_id=tenant, pos_invoice_number="POS-GP-2", opening_id=opening.opening_id,
        customer_id=customer.customer_id, posting_date=date(2026, 1, 8), subtotal=25, tax_amount=0,
        discount_amount=0, grand_total=25, paid_amount=0, status="RETURNED", is_return=True,
        return_against=sale.pos_invoice_number)
    db.add(returned)
    await db.flush()
    db.add(POSInvoiceItem(tenant_id=tenant, pos_invoice_id=returned.pos_invoice_id,
        source_pos_item_id=source_line.pos_item_id, item_id=item.item_id, quantity=1,
        unit_price=25, discount_pct=0, line_total=25, stock_quantity=1,
        cost_unit_stock=10, cost_amount=10, cost_valuation_method="STOCK_LEVEL",
        cost_source="POS_STOCK_LEVEL", cost_is_estimated=False))
    await db.flush()

    report = await enterprise_reports_service.run("gross-profit-analysis", db, tenant,
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31), currency="USD")
    row = report["rows"][0]
    assert row["revenue"] == Decimal("75.0000")
    assert row["recorded_cost"] == Decimal("30.0000")
    assert row["gross_profit"] == Decimal("45.0000")
    assert row["estimated_line_count"] == 0


@pytest.mark.asyncio
async def test_invoice_trends_compare_periods_filter_cancelled_and_preserve_payment_semantics(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    supplier = await _party(db, tenant, "SUPPLIER")
    db.add_all([
        SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="T-OLD",
            invoice_date=date(2025, 12, 10), due_date=date(2026, 1, 9), currency="USD",
            subtotal=80, tax_amount=0, total_amount=80, status="ISSUED"),
        SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="T-CURRENT",
            invoice_date=date(2026, 1, 10), due_date=date(2026, 2, 9), currency="USD",
            subtotal=100, tax_amount=0, total_amount=100, status="ISSUED"),
        SalesInvoice(tenant_id=tenant, customer_id=customer.customer_id, invoice_number="T-CANCELLED",
            invoice_date=date(2026, 1, 20), due_date=date(2026, 2, 19), currency="USD",
            subtotal=50, tax_amount=0, total_amount=50, status="CANCELLED"),
        SupplierInvoice(tenant_id=tenant, supplier_id=supplier.supplier_id, invoice_number="P-MATCHED",
            invoice_date=date(2026, 1, 12), due_date=date(2026, 2, 11), currency="USD",
            subtotal=150, tax_amount=0, total_amount=150, matching_status="MATCHED"),
    ])
    await db.flush()
    sales = await enterprise_reports_service.run("sales-invoice-trends", db, tenant,
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31), granularity="quarter", currency="USD")
    assert sales["comparison"]["current_amount"] == Decimal("100.0000")
    assert sales["comparison"]["previous_amount"] == Decimal("80.0000")
    assert sales["comparison"]["amount_change_percent"] == Decimal("25.00000000000000000000")
    assert sum(row["document_count"] for row in sales["series"]) == 1
    assert sales["documents"][0]["invoice_number"] == "T-CURRENT"
    purchase = await enterprise_reports_service.run("purchase-invoice-trends", db, tenant,
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31), granularity="month")
    assert purchase["series"][0]["status"] == "MATCHED"
    assert purchase["documents"][0]["settlement_note"].startswith("Matching status is not payment status")
    assert purchase["payment_semantics"].startswith("Purchase invoice matching state")


@pytest.mark.asyncio
async def test_material_request_preserves_context_uom_and_partial_remaining_amendment(party_db):
    db, tenant = party_db, uuid.uuid4()
    supplier = await _party(db, tenant, "SUPPLIER")
    item = Item(tenant_id=tenant, item_code=uuid.uuid4().hex, item_name="Case-pack material",
                stock_uom="EA", standard_rate=Decimal("2"))
    each = UOM(tenant_id=tenant, uom_name="Each", abbreviation="EA")
    pack = UOM(tenant_id=tenant, uom_name="Pack", abbreviation="PK")
    warehouse = Warehouse(tenant_id=tenant, warehouse_code="WH-1", warehouse_name="Main")
    project = Project(tenant_id=tenant, project_code="PJ-1", project_name="Build")
    cost_center = CostCenter(tenant_id=tenant, cost_center_code="CC-1", cost_center_name="Build")
    db.add_all([item, each, pack, warehouse, project, cost_center])
    await db.flush()
    db.add(UOMConversion(tenant_id=tenant, from_uom_id=pack.uom_id, to_uom_id=each.uom_id,
                         item_id=item.item_id, factor=6))
    await db.flush()
    mr = await requisition_service.create_material_request(db, tenant, "MR-F06-1",
        schedule_date=date(2026, 11, 1), required_by_date=date(2026, 11, 5), department="Maintenance",
        project_id=project.project_id, cost_center_id=cost_center.cost_center_id,
        source_warehouse_id=warehouse.warehouse_id,
        attachments=[{"file_name": "spec.pdf", "storage_key": "docs/spec.pdf"}],
        items=[{"item_id": item.item_id, "quantity": 10, "uom_id": pack.uom_id,
                "target_warehouse_id": warehouse.warehouse_id}])
    line = mr.items[0]
    assert line.uom == "PK" and line.conversion_factor == 6 and line.stock_quantity == 60
    await requisition_service.submit_material_request(db, tenant, mr.mr_id)
    po = await requisition_service.create_po_from_material_request(db, tenant, mr.mr_id,
        supplier.supplier_id, "PO-F06-1", [{"mr_item_id": line.mr_item_id, "quantity": 4}])
    po_line = await db.scalar(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.po_id))
    assert po_line.conversion_factor == 6 and po_line.stock_quantity == 24
    assert po.required_by_date == date(2026, 11, 5)
    assert po.project_id == project.project_id and po.cost_center_id == cost_center.cost_center_id
    assert po.attachments == [{"file_name": "spec.pdf", "storage_key": "docs/spec.pdf"}]
    with pytest.raises(ValueError, match="exceeds pending quantity"):
        await requisition_service.create_po_from_material_request(db, tenant, mr.mr_id,
            supplier.supplier_id, "PO-F06-OVER", [{"mr_item_id": line.mr_item_id, "quantity": 7}])
    amendment = await requisition_service.amend_material_request(db, tenant, mr.mr_id, "MR-F06-2")
    amended_line = amendment.items[0]
    assert amendment.amended_from_mr_id == mr.mr_id
    assert amended_line.source_mr_item_id == line.mr_item_id
    assert amended_line.quantity == 6 and amended_line.stock_quantity == 36


@pytest.mark.asyncio
async def test_supplier_quote_uom_and_awarded_po_provenance(party_db):
    db, tenant = party_db, uuid.uuid4()
    supplier = await _party(db, tenant, "SUPPLIER")
    item = Item(tenant_id=tenant, item_code=uuid.uuid4().hex, item_name="Quoted case-pack",
                stock_uom="EA", standard_rate=Decimal("1"), is_purchase_item=True)
    each = UOM(tenant_id=tenant, uom_name="Each", abbreviation="EA")
    case = UOM(tenant_id=tenant, uom_name="Case", abbreviation="CS")
    db.add_all([item, each, case])
    await db.flush()
    db.add(UOMConversion(tenant_id=tenant, from_uom_id=case.uom_id, to_uom_id=each.uom_id,
                         item_id=item.item_id, factor=12))
    await db.flush()
    quote = await sourcing_service.create_supplier_quotation(db, tenant, "SQ-F08-1", supplier.supplier_id,
        currency="USD", items=[{"item_id": item.item_id, "quantity": 5, "unit_price": 24,
                                "uom_id": case.uom_id}])
    quote_line = quote.items[0]
    assert quote_line.conversion_factor == 12 and quote_line.stock_quantity == 60
    po = await sourcing_service.award_quotation_to_po(db, tenant, quote.sq_id, "PO-F08-1")
    po_line = await db.scalar(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.po_id))
    assert po.supplier_quotation_id == quote.sq_id
    assert po_line.supplier_quotation_item_id == quote_line.sq_item_id
    assert po_line.uom_id == case.uom_id and po_line.conversion_factor == 12 and po_line.stock_quantity == 60
    with pytest.raises(ValueError, match="awarded only once"):
        await sourcing_service.award_quotation_to_po(db, tenant, quote.sq_id, "PO-F08-DUP")


@pytest.mark.asyncio
async def test_049_material_request_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/049_material_request_context.py"
    spec = importlib.util.spec_from_file_location("migration_049", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_050_supplier_quote_uom_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/050_supplier_quote_uom_provenance.py"
    spec = importlib.util.spec_from_file_location("migration_050", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_055_customer_advance_account_and_legacy_ap_reclassification(party_db):
    db, tenant = party_db, uuid.uuid4()
    account = Account(tenant_id=tenant, account_code="1200-AR-CUSTOMERS",
        account_name="Accounts Receivable", account_type="ASSET", currency="USD", is_active=True)
    db.add(account)
    await db.flush()
    legacy_source = uuid.uuid4()
    await db.execute(text("""INSERT INTO general_ledger_entries
        (entry_id,tenant_id,transaction_id,posting_date,fiscal_year,fiscal_period,account_code,cost_center,
         debit_amount,credit_amount,currency,exchange_rate,source_document_type,source_document_id,period_closing_locked)
        VALUES (:id,:tenant,:tx,'2026-01-01',2026,1,'2000-ACCOUNTS-PAYABLE','TEST',20,0,'USD',1,'DEBIT_NOTE',:source,false)
    """), {"id": uuid.uuid4(), "tenant": tenant, "tx": uuid.uuid4(), "source": legacy_source})

    filename = Path(__file__).resolve().parents[1] / "alembic/versions/055_customer_advance_ledger.py"
    spec = importlib.util.spec_from_file_location("migration_055", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await db.connection()

    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()

    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)
    advance = await db.scalar(select(Account).where(
        Account.tenant_id == tenant, Account.account_code == "2150-CUSTOMER-ADVANCES",
    ))
    assert advance is not None and advance.account_type == "LIABILITY" and advance.currency == "USD"
    assert await db.scalar(select(GL.account_code).where(GL.source_document_id == legacy_source)) == "2100-AP-VENDORS"


@pytest.mark.asyncio
async def test_056_pos_cost_and_return_lineage_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/056_pos_cost_and_return_lineage.py"
    spec = importlib.util.spec_from_file_location("migration_056", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()

    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()

    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_057_work_order_production_plan_link_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/057_work_order_production_plan_link.py"
    spec = importlib.util.spec_from_file_location("migration_057", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()

    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()

    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)
    columns, foreign_keys = await connection.run_sync(
        lambda sync_connection: (
            {column["name"] for column in sa_inspect(sync_connection).get_columns("work_orders")},
            sa_inspect(sync_connection).get_foreign_keys("work_orders"),
        )
    )
    assert "production_plan_id" in columns
    assert any(
        fk["name"] == "fk_work_order_production_plan"
        and fk["constrained_columns"] == ["production_plan_id"]
        and fk["referred_table"] == "production_plans"
        for fk in foreign_keys
    )


@pytest.mark.asyncio
async def test_bundle_snapshot_expands_stock_uom_and_cost_without_mutable_master_lookup(party_db):
    db, tenant = party_db, uuid.uuid4()
    parent = Item(tenant_id=tenant, item_code="BUNDLE-PARENT", item_name="Starter Kit", stock_uom="EA")
    component = Item(tenant_id=tenant, item_code="BUNDLE-COMP", item_name="Kit Component", stock_uom="EA")
    each = UOM(tenant_id=tenant, uom_name="Each", abbreviation="EA")
    pack = UOM(tenant_id=tenant, uom_name="Pack", abbreviation="PK")
    db.add_all([parent, component, each, pack])
    await db.flush()
    bundle = ProductBundle(tenant_id=tenant, bundle_item_id=parent.item_id, bundle_name="Starter Kit")
    db.add(bundle)
    await db.flush()
    db.add_all([
        UOMConversion(tenant_id=tenant, from_uom_id=pack.uom_id, to_uom_id=each.uom_id,
                      item_id=component.item_id, factor=6),
        UOMConversion(tenant_id=tenant, from_uom_id=pack.uom_id, to_uom_id=each.uom_id,
                      item_id=parent.item_id, factor=3),
        ProductBundleItem(tenant_id=tenant, bundle_id=bundle.bundle_id, item_id=component.item_id,
                          quantity=2, uom_id=pack.uom_id),
    ])
    await db.flush()
    snapshot = await snapshot_bundle_components(db, tenant, parent.item_id)
    assert snapshot and Decimal(snapshot[0]["stock_quantity_per_bundle"]) == 12
    assert bundle_stock_requirements(snapshot, Decimal("3")) == {component.item_id: Decimal("36")}
    delivery_snapshot, total_stock, total_cost = bundle_delivery_snapshot(
        snapshot, Decimal("3"), {component.item_id: type("Stock", (), {"valuation_rate": Decimal("5")})()})
    assert total_stock == 36 and total_cost == 180
    assert Decimal(delivery_snapshot[0]["cost_amount"]) == 180


@pytest.mark.asyncio
async def test_bundle_order_reserves_and_partially_delivers_component_stock(party_db):
    db, tenant = party_db, uuid.uuid4()
    db.add(Tenant(tenant_id=tenant, tenant_slug=uuid.uuid4().hex,
                  company_name="Bundle Acceptance Tenant", currency="USD"))
    await db.flush()
    parent = Item(tenant_id=tenant, item_code="BUNDLE-PARENT-2", item_name="Starter Kit", stock_uom="EA")
    component = Item(tenant_id=tenant, item_code="BUNDLE-COMP-2", item_name="Kit Component", stock_uom="EA")
    each = UOM(tenant_id=tenant, uom_name="Each", abbreviation="EA")
    pack = UOM(tenant_id=tenant, uom_name="Pack", abbreviation="PK")
    customer = Customer(tenant_id=tenant, customer_code="BUNDLE-CUSTOMER", customer_name="Bundle Buyer", credit_limit=Decimal("10000"))
    warehouse = Warehouse(tenant_id=tenant, warehouse_code="BUNDLE-WH", warehouse_name="Bundle Warehouse")
    db.add_all([parent, component, each, pack, customer, warehouse])
    await db.flush()
    bundle = ProductBundle(tenant_id=tenant, bundle_item_id=parent.item_id, bundle_name="Starter Kit")
    db.add(bundle)
    await db.flush()
    db.add_all([
        UOMConversion(tenant_id=tenant, from_uom_id=pack.uom_id, to_uom_id=each.uom_id,
                      item_id=component.item_id, factor=6),
        UOMConversion(tenant_id=tenant, from_uom_id=pack.uom_id, to_uom_id=each.uom_id,
                      item_id=parent.item_id, factor=3),
        ProductBundleItem(tenant_id=tenant, bundle_id=bundle.bundle_id, item_id=component.item_id,
                          quantity=2, uom_id=pack.uom_id),
    ])
    await db.flush()
    snapshot = await snapshot_bundle_components(db, tenant, parent.item_id)
    stock = StockLevel(tenant_id=tenant, item_id=component.item_id, warehouse_id=warehouse.warehouse_id,
                       current_qty=Decimal("72"), available_qty=Decimal("72"), valuation_rate=Decimal("5"))
    db.add(stock)
    await db.flush()
    quote = await create_sales_quote(CreateSalesQuoteRequest(
        quotation_number="QT-BUNDLE-1", customer_id=customer.customer_id,
        quotation_date=date.today(), valid_until=date.today(), currency="USD",
        items=[SalesQuoteLineSpec(item_id=parent.item_id, quantity=Decimal("2"),
                                  unit_price=Decimal("40"), uom_id=pack.uom_id)],
    ), tenant, db)
    quote_line = await db.scalar(select(SalesQuotationItem).where(
        SalesQuotationItem.quotation_id == quote.quotation_id,
    ))
    assert quote_line.bundle_components_snapshot == snapshot
    assert quote_line.stock_quantity == Decimal("6.0000")
    reviewer = SimpleNamespace(tenant_id=tenant)
    order = await convert_quote_to_order(quote.quotation_id, ConvertQuoteToOrderRequest(
        order_number="SO-BUNDLE-1", items=[QuoteItemSpec(quotation_item_id=quote_line.quotation_item_id,
        item_id=parent.item_id, quantity=Decimal("2"), unit_price=Decimal("40"))],
        warehouse_id=warehouse.warehouse_id), tenant, db, reviewer)
    order_line = await db.scalar(select(SalesOrderItem).where(SalesOrderItem.order_id == order.order_id))
    await db.refresh(stock)
    assert stock.reserved_qty == 72 and stock.available_qty == 0
    assert order.total_amount == 80 and order_line.stock_quantity == 6 and order_line.conversion_factor == 3

    insufficient_quote = SalesQuotation(tenant_id=tenant, quotation_number="QT-BUNDLE-SHORT", customer_id=customer.customer_id,
        quotation_date=date.today(), valid_until=date.today(), subtotal=Decimal("40"), tax_amount=Decimal("0"),
        total_amount=Decimal("40"), currency="USD", status="OFFICIAL")
    db.add(insufficient_quote)
    await db.flush()
    insufficient_line = SalesQuotationItem(tenant_id=tenant, quotation_id=insufficient_quote.quotation_id,
        item_id=parent.item_id, quantity=Decimal("1"), unit_price=Decimal("40"), line_total=Decimal("40"),
        uom_id=pack.uom_id, conversion_factor=Decimal("3"), stock_quantity=Decimal("3"),
        bundle_components_snapshot=snapshot)
    db.add(insufficient_line)
    await db.flush()
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as rejected:
        await convert_quote_to_order(insufficient_quote.quotation_id, ConvertQuoteToOrderRequest(
            order_number="SO-BUNDLE-SHORT", items=[QuoteItemSpec(quotation_item_id=insufficient_line.quotation_item_id,
            item_id=parent.item_id, quantity=Decimal("1"), unit_price=Decimal("40"))],
            warehouse_id=warehouse.warehouse_id), tenant, db, reviewer)
    assert rejected.value.status_code == 409
    delivery = await fulfill_sales_order(order.order_id, FulfillOrderRequest(
        warehouse_id=warehouse.warehouse_id,
        items=[FulfillOrderItemRequest(order_item_id=order_line.order_item_id, quantity=Decimal("1"))],
    ), tenant, db)
    await db.refresh(stock)
    await db.refresh(order_line)
    delivery_line = await db.scalar(select(DeliveryNoteItem).where(DeliveryNoteItem.delivery_note_id == delivery.delivery_note_id))
    assert stock.current_qty == 36 and stock.reserved_qty == 36
    assert order_line.delivered_quantity == 1
    assert delivery_line.item_id == parent.item_id and delivery_line.quantity == 1
    assert delivery_line.cost_amount == 180 and delivery_line.cost_source == "BUNDLE_COMPONENTS"
    assert Decimal(delivery_line.bundle_components_snapshot[0]["stock_quantity"]) == 36
    final_delivery = await fulfill_sales_order(order.order_id, FulfillOrderRequest(
        warehouse_id=warehouse.warehouse_id,
        items=[FulfillOrderItemRequest(order_item_id=order_line.order_item_id, quantity=Decimal("1"))],
    ), tenant, db)
    await db.flush()
    await db.refresh(stock)
    delivered_quantity = await db.scalar(select(SalesOrderItem.delivered_quantity).where(SalesOrderItem.order_item_id == order_line.order_item_id))
    order_status = await db.scalar(select(SalesOrder.status).where(SalesOrder.order_id == order.order_id))
    assert stock.current_qty == 0 and stock.reserved_qty == 0
    assert delivered_quantity == 2 and order_status == "DELIVERED"
    assert await db.scalar(select(DeliveryNoteItem.dn_item_id).where(DeliveryNoteItem.delivery_note_id == final_delivery.delivery_note_id))

    # Exercise the live delivery-to-invoice path with a real ledger posting.
    ar = Account(tenant_id=tenant, account_code="AR-1000", account_name="Accounts Receivable",
                 account_type="ASSET", currency="USD")
    revenue = Account(tenant_id=tenant, account_code="REV-4000", account_name="Sales Revenue",
                      account_type="REVENUE", currency="USD")
    cost_center = CostCenter(tenant_id=tenant, cost_center_code="BUNDLE-CC", cost_center_name="Bundle Sales")
    db.add_all([ar, revenue, cost_center])
    await db.flush()
    invoice = await create_sales_invoice_from_delivery(
        final_delivery.delivery_note_id,
        CreateSalesInvoiceRequest(invoice_number="INV-BUNDLE-LIVE"),
        tenant, db,
    )
    await db.flush()
    invoice_line = await db.scalar(select(SalesInvoiceItem).where(
        SalesInvoiceItem.invoice_id == invoice.invoice_id,
    ))
    invoice_gl = (await db.scalars(select(GL).where(
        GL.tenant_id == tenant,
        GL.source_document_type == "SALES_INVOICE",
        GL.source_document_id == invoice.invoice_id,
    ))).all()
    assert invoice_line.bundle_components_snapshot == delivery_line.bundle_components_snapshot
    assert invoice_line.cost_amount == delivery_line.cost_amount == Decimal("180.0000")
    assert sum((entry.debit_amount for entry in invoice_gl), Decimal("0")) == Decimal("40.0000")
    assert sum((entry.credit_amount for entry in invoice_gl), Decimal("0")) == Decimal("40.0000")
    delivery_rows = await list_delivery_notes(tenant, db)
    listed_delivery = next(row for row in delivery_rows if row["delivery_note_id"] == final_delivery.delivery_note_id)
    assert listed_delivery["items"][0]["bundle_components_snapshot"] == delivery_line.bundle_components_snapshot
    timeline = await sales_order_timeline(order.order_id, tenant, db)
    assert timeline["sales_invoices"][0]["items"][0]["bundle_components_snapshot"] == invoice_line.bundle_components_snapshot

    stock.current_qty = Decimal("36")
    stock.available_qty = Decimal("36")
    cancellable_quote = SalesQuotation(tenant_id=tenant, quotation_number="QT-BUNDLE-CANCEL", customer_id=customer.customer_id,
        quotation_date=date.today(), valid_until=date.today(), subtotal=Decimal("40"), tax_amount=Decimal("0"),
        total_amount=Decimal("40"), currency="USD", status="OFFICIAL")
    db.add(cancellable_quote)
    await db.flush()
    cancellable_line = SalesQuotationItem(tenant_id=tenant, quotation_id=cancellable_quote.quotation_id,
        item_id=parent.item_id, quantity=Decimal("1"), unit_price=Decimal("40"), line_total=Decimal("40"),
        uom_id=pack.uom_id, conversion_factor=Decimal("3"), stock_quantity=Decimal("3"),
        bundle_components_snapshot=snapshot)
    db.add(cancellable_line)
    await db.flush()
    cancellable_order = await convert_quote_to_order(cancellable_quote.quotation_id, ConvertQuoteToOrderRequest(
        order_number="SO-BUNDLE-CANCEL", items=[QuoteItemSpec(quotation_item_id=cancellable_line.quotation_item_id,
        item_id=parent.item_id, quantity=Decimal("1"), unit_price=Decimal("40"))],
        warehouse_id=warehouse.warehouse_id), tenant, db, reviewer)
    await db.refresh(stock)
    assert stock.reserved_qty == 36
    cancelled = await cancel_sales_order(cancellable_order.order_id, tenant, db)
    await db.flush()
    await db.refresh(stock)
    assert cancelled.status == "CANCELLED" and stock.reserved_qty == 0 and stock.available_qty == 36


@pytest.mark.asyncio
async def test_bundle_credit_note_restores_component_stock_from_frozen_invoice_snapshot(party_db):
    db, tenant = party_db, uuid.uuid4()
    customer = await _party(db, tenant, "CUSTOMER")
    parent = Item(tenant_id=tenant, item_code="BUNDLE-RETURN-PARENT", item_name="Starter Kit", stock_uom="EA")
    component = Item(tenant_id=tenant, item_code="BUNDLE-RETURN-COMP", item_name="Kit Component", stock_uom="EA")
    warehouse = Warehouse(tenant_id=tenant, warehouse_code="BUNDLE-RETURN-WH", warehouse_name="Returns Warehouse")
    db.add_all([parent, component, warehouse])
    await db.flush()
    stock = StockLevel(tenant_id=tenant, item_id=component.item_id, warehouse_id=warehouse.warehouse_id,
                       current_qty=Decimal("0"), available_qty=Decimal("0"), valuation_rate=Decimal("5"))
    invoice = SalesInvoice(tenant_id=tenant, invoice_number="INV-BUNDLE-RETURN", customer_id=customer.customer_id,
        invoice_date=date.today(), due_date=date.today(), currency="USD", subtotal=Decimal("80"),
        tax_amount=Decimal("0"), total_amount=Decimal("80"), status="ISSUED")
    db.add_all([stock, invoice])
    await db.flush()
    invoice_line = SalesInvoiceItem(tenant_id=tenant, invoice_id=invoice.invoice_id, item_id=parent.item_id,
        quantity=Decimal("2"), unit_price=Decimal("40"), line_total=Decimal("80"),
        stock_quantity=Decimal("24"), cost_amount=Decimal("120"), cost_is_estimated=False,
        bundle_components_snapshot=[{"item_id": str(component.item_id), "item_name": component.item_name,
            "quantity": "4", "stock_quantity": "24", "cost_unit_stock": "5", "cost_amount": "120"}])
    db.add(invoice_line)
    await db.flush()

    class _NoopLedger:
        async def commit_transaction(self, session, proposal):
            return uuid.uuid4()

    credit_note = await ReturnsService(ledger_engine=_NoopLedger()).issue_credit_note(
        db, tenant, customer.customer_id, "Bundle return", [{"item_id": parent.item_id, "quantity": 1,
        "sales_invoice_item_id": invoice_line.invoice_item_id}], invoice_id=invoice.invoice_id, warehouse_id=warehouse.warehouse_id)
    await db.flush()
    await db.refresh(stock)
    assert Decimal(credit_note.items[0].bundle_components_snapshot[0]["stock_quantity"]) == 12
    assert stock.current_qty == 12 and stock.available_qty == 12


@pytest.mark.asyncio
async def test_051_bundle_snapshot_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/051_product_bundle_snapshots.py"
    spec = importlib.util.spec_from_file_location("migration_051", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_052_pos_commercial_snapshot_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/052_pos_commercial_snapshots.py"
    spec = importlib.util.spec_from_file_location("migration_052", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_053_pos_bundle_snapshot_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/053_pos_bundle_snapshots.py"
    spec = importlib.util.spec_from_file_location("migration_053", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_054_pos_profile_price_list_migration_executes(party_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/054_pos_profile_price_list.py"
    spec = importlib.util.spec_from_file_location("migration_054", filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await party_db.connection()
    def run_migration(sync_connection, operation):
        with Operations.context(MigrationContext.configure(sync_connection)):
            operation()
    await connection.run_sync(run_migration, migration.downgrade)
    await connection.run_sync(run_migration, migration.upgrade)


@pytest.mark.asyncio
async def test_pos_uses_tenant_selling_default_and_preserves_uom_rate_snapshot(party_db):
    db = party_db
    tenant = Tenant(tenant_slug=uuid.uuid4().hex, company_name="POS parity tenant", currency="USD")
    db.add(tenant)
    await db.flush()
    user = User(tenant_id=tenant.tenant_id, email=f"{uuid.uuid4().hex}@example.test",
                hashed_password="test", full_name="POS Clerk")
    warehouse = Warehouse(tenant_id=tenant.tenant_id, warehouse_code="POS-WH", warehouse_name="POS warehouse")
    customer = Customer(tenant_id=tenant.tenant_id, customer_code="POS-CUST", customer_name="POS Customer")
    item = Item(tenant_id=tenant.tenant_id, item_code="POS-ITEM", item_name="POS Item", stock_uom="EA", standard_rate=Decimal("8"))
    each = UOM(tenant_id=tenant.tenant_id, uom_name="Each", abbreviation="EA")
    box = UOM(tenant_id=tenant.tenant_id, uom_name="Box", abbreviation="BOX")
    price_list = PriceList(tenant_id=tenant.tenant_id, price_list_name="Retail Default", currency="USD", selling=True)
    settings = TenantSettings(tenant_id=tenant.tenant_id, default_selling_price_list="Retail Default")
    db.add_all([user, warehouse, customer, item, each, box, price_list, settings])
    await db.flush()
    db.add_all([
        UOMConversion(tenant_id=tenant.tenant_id, from_uom_id=box.uom_id, to_uom_id=each.uom_id,
                      item_id=item.item_id, factor=4),
        ItemPrice(tenant_id=tenant.tenant_id, item_id=item.item_id, price_list_id=price_list.price_list_id,
                  uom_id=box.uom_id, rate=Decimal("30"), currency="USD", priority=1),
    ])
    profile = POSProfile(tenant_id=tenant.tenant_id, profile_name="Retail POS", warehouse_id=warehouse.warehouse_id,
                         currency="USD", allow_rate_change=False)
    db.add(profile)
    await db.flush()
    stock = StockLevel(tenant_id=tenant.tenant_id, item_id=item.item_id, warehouse_id=warehouse.warehouse_id,
                       current_qty=Decimal("100"), available_qty=Decimal("100"), valuation_rate=Decimal("5"))
    db.add(stock)
    await db.flush()
    shift = await POSService().open_shift(db, tenant.tenant_id, profile.profile_id, user.user_id, Decimal("0"))
    invoice, _ = await POSService().process_pos_sale(db, tenant.tenant_id, shift.opening_id,
        customer.customer_id, items=[{"item_id": item.item_id, "quantity": Decimal("2"),
        "unit_price": Decimal("99"), "uom_id": box.uom_id}])
    await db.flush()
    await db.refresh(stock)
    assert invoice.subtotal == Decimal("60.0000")
    assert invoice.price_list_id == price_list.price_list_id
    assert invoice.items[0].uom_id == box.uom_id
    assert invoice.items[0].conversion_factor == Decimal("4.00000000")
    assert invoice.items[0].stock_quantity == Decimal("8.0000")
    assert invoice.items[0].price_list_rate == Decimal("30.0000")
    assert stock.current_qty == Decimal("92.0000")

    explicit_list = PriceList(tenant_id=tenant.tenant_id, price_list_name="POS Explicit", currency="USD", selling=True)
    db.add(explicit_list)
    await db.flush()
    db.add(ItemPrice(tenant_id=tenant.tenant_id, item_id=item.item_id, price_list_id=explicit_list.price_list_id,
                     rate=Decimal("35"), currency="USD", priority=1))
    profile.price_list_id = explicit_list.price_list_id
    await db.flush()
    explicit_invoice, _ = await POSService().process_pos_sale(db, tenant.tenant_id, shift.opening_id,
        customer.customer_id, items=[{"item_id": item.item_id, "quantity": Decimal("1"), "unit_price": Decimal("1")}])
    await db.flush()
    assert explicit_invoice.price_list_id == explicit_list.price_list_id
    assert explicit_invoice.items[0].price_list_rate == Decimal("35.0000")

    # Returns use the original positive entered quantity; the return flag drives
    # stock direction, while the original UOM factor restores stock units.
    return_invoice, _ = await POSService().process_pos_sale(db, tenant.tenant_id, shift.opening_id,
        customer.customer_id, items=[{"item_id": item.item_id, "quantity": Decimal("1"),
        "unit_price": Decimal("30"), "uom_id": box.uom_id}], is_return=True,
        return_against=str(invoice.pos_invoice_id))
    await db.flush()
    await db.refresh(stock)
    assert return_invoice.is_return is True
    assert return_invoice.items[0].stock_quantity == Decimal("4.0000")
    assert stock.current_qty == Decimal("95.0000")
    assert return_invoice.price_list_id == price_list.price_list_id


@pytest.mark.asyncio
async def test_pos_bundle_sale_and_return_use_frozen_component_recipe(party_db):
    db = party_db
    tenant = Tenant(tenant_slug=uuid.uuid4().hex, company_name="POS bundle tenant", currency="USD")
    db.add(tenant)
    await db.flush()
    user = User(tenant_id=tenant.tenant_id, email=f"{uuid.uuid4().hex}@example.test",
                hashed_password="test", full_name="POS Bundle Clerk")
    warehouse = Warehouse(tenant_id=tenant.tenant_id, warehouse_code="POS-BUNDLE-WH", warehouse_name="POS bundle warehouse")
    customer = Customer(tenant_id=tenant.tenant_id, customer_code="POS-BUNDLE-CUST", customer_name="POS Bundle Customer")
    parent = Item(tenant_id=tenant.tenant_id, item_code="POS-BUNDLE", item_name="POS Bundle", stock_uom="EA",
                  standard_rate=Decimal("25"), is_sales_item=True, is_stock_item=True)
    component = Item(tenant_id=tenant.tenant_id, item_code="POS-BUNDLE-COMP", item_name="POS Bundle Component",
                     stock_uom="EA", is_sales_item=True, is_stock_item=True)
    price_list = PriceList(tenant_id=tenant.tenant_id, price_list_name="Bundle Retail", currency="USD", selling=True)
    settings = TenantSettings(tenant_id=tenant.tenant_id, default_selling_price_list="Bundle Retail")
    db.add_all([user, warehouse, customer, parent, component, price_list, settings])
    await db.flush()
    db.add_all([
        ItemPrice(tenant_id=tenant.tenant_id, item_id=parent.item_id, price_list_id=price_list.price_list_id,
                  rate=Decimal("25"), currency="USD"),
        StockLevel(tenant_id=tenant.tenant_id, item_id=parent.item_id, warehouse_id=warehouse.warehouse_id,
                   current_qty=Decimal("10"), available_qty=Decimal("10"), valuation_rate=Decimal("1")),
        StockLevel(tenant_id=tenant.tenant_id, item_id=component.item_id, warehouse_id=warehouse.warehouse_id,
                   current_qty=Decimal("10"), available_qty=Decimal("10"), valuation_rate=Decimal("3")),
    ])
    bundle = ProductBundle(tenant_id=tenant.tenant_id, bundle_item_id=parent.item_id, bundle_name="Retail Starter")
    profile = POSProfile(tenant_id=tenant.tenant_id, profile_name="Bundle POS", warehouse_id=warehouse.warehouse_id,
                         currency="USD", allow_rate_change=False)
    db.add_all([bundle, profile])
    await db.flush()
    recipe = ProductBundleItem(tenant_id=tenant.tenant_id, bundle_id=bundle.bundle_id,
                               item_id=component.item_id, quantity=2)
    db.add(recipe)
    await db.flush()
    parent_stock = await db.scalar(select(StockLevel).where(StockLevel.item_id == parent.item_id))
    component_stock = await db.scalar(select(StockLevel).where(StockLevel.item_id == component.item_id))
    shift = await POSService().open_shift(db, tenant.tenant_id, profile.profile_id, user.user_id, Decimal("0"))

    invoice, _ = await POSService().process_pos_sale(db, tenant.tenant_id, shift.opening_id,
        customer.customer_id, items=[{"item_id": parent.item_id, "quantity": Decimal("2"), "unit_price": Decimal("99")}])
    await db.flush()
    await db.refresh(parent_stock)
    await db.refresh(component_stock)
    snapshot = invoice.items[0].bundle_components_snapshot
    assert snapshot and Decimal(snapshot[0]["stock_quantity_per_bundle"]) == Decimal("2")
    assert parent_stock.current_qty == Decimal("10.0000")  # sellable parent is not a stock movement
    assert component_stock.current_qty == Decimal("6.0000")

    # A master recipe edit after checkout must not change what the receipt return restores.
    recipe.quantity = Decimal("9")
    await db.flush()
    returned, _ = await POSService().process_pos_sale(db, tenant.tenant_id, shift.opening_id,
        customer.customer_id, items=[{"item_id": parent.item_id, "quantity": Decimal("1"), "unit_price": Decimal("25")}],
        is_return=True, return_against=str(invoice.pos_invoice_id))
    await db.flush()
    await db.refresh(component_stock)
    assert Decimal(returned.items[0].bundle_components_snapshot[0]["quantity_per_bundle"]) == Decimal("2")
    assert component_stock.current_qty == Decimal("8.0000")


def test_party_and_settlement_references_must_be_complete():
    base = {"account_code": "AR", "cost_center": "TEST", "debit_amount": 1}
    for extra in ({"party_type": "CUSTOMER"}, {"party_id": uuid.uuid4()},
                  {"against_document_type": "SALES_INVOICE", "against_document_id": uuid.uuid4()},
                  {"party_type": "CUSTOMER", "party_id": uuid.uuid4(),
                   "against_document_type": "SUPPLIER_INVOICE", "against_document_id": uuid.uuid4()}):
        with pytest.raises(ValidationError):
            LedgerLineProposal(**base, **extra)
