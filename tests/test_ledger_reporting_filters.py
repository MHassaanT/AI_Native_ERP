"""Exercise report SQL on isolated SQLite data, including legacy source links."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import JSON, Column, MetaData, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from erp.db.models.billing import (
    CreditNote,
    CreditNoteItem,
    DebitNote,
    DebitNoteItem,
    POSInvoice,
    POSInvoiceItem,
)
from erp.db.models.inventory import Item, StockLedgerEntry, Warehouse
from erp.db.models.ledger import Account
from erp.db.models.ledger import GeneralLedgerEntry as GL
from erp.db.models.purchasing import SupplierInvoice, SupplierInvoiceItem
from erp.db.models.sales import SalesInvoice, SalesInvoiceItem
from erp.db.models.subcontracting import SubcontractingOrder, SubcontractingReceipt
from erp.workflows.reports.financial_reports_service import FinancialReportsService
from erp.workflows.reports.general_ledger_service import LedgerFilters, query_ledger


@pytest_asyncio.fixture
async def report_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    metadata = MetaData()
    # Only the schema required by report queries, without unrelated domain FKs
    # or PostgreSQL defaults. Actual report SQL is executed, rather than mocked.
    for model in (Item, Warehouse, GL, Account, SalesInvoice, SalesInvoiceItem, SupplierInvoice, SupplierInvoiceItem,
                  POSInvoice, POSInvoiceItem, CreditNote, CreditNoteItem, DebitNote, DebitNoteItem,
                  StockLedgerEntry, SubcontractingOrder, SubcontractingReceipt):
        Table(model.__tablename__, metadata, *(Column(c.name,
            JSON() if isinstance(c.type, JSONB) else c.type,
            primary_key=c.primary_key, nullable=not c.primary_key) for c in model.__table__.columns))
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


def entry(tenant, account, dr=0, cr=0, day="2026-10-15", **extra):
    return GL(tenant_id=tenant, transaction_id=uuid.uuid4(), entry_id=uuid.uuid4(),
              posting_date=date.fromisoformat(day), fiscal_year=2026, fiscal_period=10,
              account_code=account, cost_center="MAIN", debit_amount=Decimal(dr), credit_amount=Decimal(cr),
              currency="USD", source_document_type="MANUAL_JOURNAL", source_document_id=uuid.uuid4(),
              created_at=datetime.now(UTC), **extra)


async def journal(session, tenant, amount=10, **values):
    dr, cr = entry(tenant, "1000-CASH", dr=amount), entry(tenant, "4000-SALES", cr=amount)
    cr.transaction_id = dr.transaction_id
    cr.source_document_id = dr.source_document_id
    for row in (dr, cr):
        for key, value in values.items():
            setattr(row, key, value)
    session.add_all([dr, cr])
    await session.flush()
    return dr, cr


@pytest.mark.asyncio
async def test_pagination_totals_currency_and_unfiltered_counterparts(report_db):
    tenant = uuid.uuid4()
    dr, _ = await journal(report_db, tenant, 12, purpose="Office supplies")
    await journal(report_db, tenant, 3)
    await journal(report_db, tenant, 90, currency="PKR")
    await journal(report_db, uuid.uuid4(), 999)
    result = await query_ledger(report_db, tenant, LedgerFilters(account_code="1000-CASH", currency="USD"), limit=1)
    assert len(result["entries"]) == 1
    assert result["total"] == 2
    assert result["totals"] == [{"currency": "USD", "debit": Decimal(15), "credit": Decimal(0)}]
    assert result["counterparts"][result["entries"][0].transaction_id]["from_accounts"] == {"4000-SALES"}
    result = await query_ledger(report_db, tenant, LedgerFilters(transaction_id=dr.transaction_id))
    assert all(row.purpose == "Office supplies" for row in result["entries"])
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_party_sources_and_control_leg_select_full_journal(report_db):
    tenant, customer, supplier = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    dr, cr = await journal(report_db, tenant)
    dr.party_type, dr.party_id, dr.party_name_snapshot = "CUSTOMER", customer, "Customer A"
    legacy_id = uuid.uuid4()
    await report_db.execute(POSInvoice.__table__.insert().values(
        tenant_id=tenant, pos_invoice_id=legacy_id, customer_id=customer))
    await journal(report_db, tenant, source_document_type="POS_INVOICE", source_document_id=legacy_id)
    await journal(report_db, tenant, source_document_type="DEBIT_NOTE")
    result = await query_ledger(report_db, tenant, LedgerFilters(customer_id=customer))
    assert result["total"] == 4
    assert cr.party_id is None  # Counterpart never becomes a party control leg.
    assert (await query_ledger(report_db, tenant, LedgerFilters(supplier_id=supplier)))["total"] == 0
    assert (await query_ledger(report_db, tenant, LedgerFilters(activity="BUYING")))["total"] == 2
    assert (await query_ledger(report_db, tenant, LedgerFilters(customer_id=customer, activity="SALES")))["total"] == 2


@pytest.mark.asyncio
async def test_item_warehouse_lineage_and_tenant_isolation(report_db):
    tenant, other, doc = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    item, warehouse, second_item, second_warehouse = [uuid.uuid4() for _ in range(4)]
    await journal(report_db, tenant, source_document_type="POS_INVOICE", source_document_id=doc)
    for item_id, warehouse_id, stock_tenant in ((item, warehouse, tenant), (second_item, second_warehouse, tenant), (second_item, warehouse, other)):
        await report_db.execute(StockLedgerEntry.__table__.insert().values(
            tenant_id=stock_tenant, item_id=item_id, warehouse_id=warehouse_id,
            source_document_type="POS_INVOICE", source_document_id=doc))
    assert (await query_ledger(report_db, tenant, LedgerFilters(item_id=item, warehouse_id=warehouse)))["total"] == 2
    assert (await query_ledger(report_db, tenant, LedgerFilters(item_id=second_item, warehouse_id=warehouse)))["total"] == 0
    # No stock movement is required for a non-stock invoice's item filter.
    invoice = uuid.uuid4()
    await report_db.execute(SalesInvoiceItem.__table__.insert().values(tenant_id=tenant, invoice_id=invoice, item_id=item))
    await journal(report_db, tenant, source_document_type="SALES_INVOICE", source_document_id=invoice)
    assert (await query_ledger(report_db, tenant, LedgerFilters(item_id=item)))["total"] == 4


@pytest.mark.asyncio
async def test_contractor_and_linked_receipt_dimensions(report_db):
    tenant, contractor, order, receipt, item, warehouse = [uuid.uuid4() for _ in range(6)]
    await report_db.execute(SubcontractingOrder.__table__.insert().values(tenant_id=tenant, sco_id=order, supplier_id=contractor))
    await report_db.execute(SubcontractingReceipt.__table__.insert().values(tenant_id=tenant, sco_id=order, scr_id=receipt))
    await report_db.execute(StockLedgerEntry.__table__.insert().values(tenant_id=tenant, item_id=item,
        warehouse_id=warehouse, source_document_type="SUBCONTRACTING_RECEIPT_FG", source_document_id=receipt))
    await journal(report_db, tenant, source_document_type="SUBCONTRACTING_RECEIPT", source_document_id=receipt)
    assert (await query_ledger(report_db, tenant, LedgerFilters(contractor_id=contractor, item_id=item, warehouse_id=warehouse)))["total"] == 2
    assert (await query_ledger(report_db, tenant, LedgerFilters(contractor_id=uuid.uuid4())))["total"] == 0


@pytest.mark.asyncio
async def test_trial_balance_opening_inclusive_period_and_closing(report_db):
    tenant = uuid.uuid4()
    await journal(report_db, tenant, 100, posting_date=date(2026, 9, 1))
    # Reduce each account's opening balance; opening must be net, not gross.
    report_db.add_all([entry(tenant, "1000-CASH", cr=40, day="2026-09-15"), entry(tenant, "4000-SALES", dr=40, day="2026-09-15")])
    await journal(report_db, tenant, 10, posting_date=date(2026, 10, 1))
    await journal(report_db, tenant, 20, posting_date=date(2026, 10, 31))
    await journal(report_db, tenant, 999, posting_date=date(2026, 11, 1))
    await journal(report_db, uuid.uuid4(), 888)
    await report_db.flush()
    report = await FinancialReportsService().get_trial_balance(report_db, tenant, date(2026, 10, 1), date(2026, 10, 31))
    cash = next(row for row in report["rows"] if row["account_code"] == "1000-CASH")
    assert (cash["opening_debit"], cash["opening_credit"], cash["period_debit"], cash["closing_debit"]) == (60, 0, 30, 90)
    assert report["totals"]["is_balanced"]
    assert report["totals"]["opening_debit"] == report["totals"]["opening_credit"] == 60
    assert (await query_ledger(report_db, tenant, LedgerFilters(from_date=date(2026, 10, 1), to_date=date(2026, 10, 31))))["total"] == 4
    with pytest.raises(ValueError, match="From date"):
        await FinancialReportsService().get_trial_balance(report_db, tenant, date(2026, 11, 1), date(2026, 10, 1))
    with pytest.raises(ValueError, match="From date"):
        await query_ledger(report_db, tenant, LedgerFilters(from_date=date(2026, 11, 1), to_date=date(2026, 10, 1)))


@pytest.mark.asyncio
async def test_sales_delivery_and_buying_grn_links(report_db):
    tenant, item, warehouse = [uuid.uuid4() for _ in range(3)]
    for source, model, field, stock_source in (
        ("SALES_INVOICE", SalesInvoice, "delivery_note_id", "DELIVERY_NOTE"),
        ("AUTOMATED_AP_MATCH", SupplierInvoice, "grn_id", "GOODS_RECEIPT"),
    ):
        invoice, movement = uuid.uuid4(), uuid.uuid4()
        await report_db.execute(model.__table__.insert().values(
            tenant_id=tenant, invoice_id=invoice, **{field: movement}))
        await report_db.execute(StockLedgerEntry.__table__.insert().values(
            tenant_id=tenant, item_id=item, warehouse_id=warehouse,
            source_document_type=stock_source, source_document_id=movement))
        await journal(report_db, tenant, source_document_type=source, source_document_id=invoice)
        filters = LedgerFilters(source_document_type=source, warehouse_id=warehouse, item_id=item)
        assert (await query_ledger(report_db, tenant, filters))["total"] == 2
        filters.item_id = uuid.uuid4()
        assert (await query_ledger(report_db, tenant, filters))["total"] == 0


@pytest.mark.asyncio
async def test_manual_dimensions_and_combined_filters(report_db):
    tenant, item, warehouse = [uuid.uuid4() for _ in range(3)]
    await journal(report_db, tenant, item_id=item, warehouse_id=warehouse, purpose="Materials transfer")
    result = await query_ledger(report_db, tenant, LedgerFilters(item_id=item, warehouse_id=warehouse,
        account_code="1000-CASH", cost_center="MAIN", source_document_type="MANUAL_JOURNAL"))
    assert result["total"] == 1
    assert result["entries"][0].purpose == "Materials transfer"
    assert result["entries"][0].warehouse_id == warehouse
    assert (await query_ledger(report_db, tenant, LedgerFilters(cost_center="OTHER")))["total"] == 0


@pytest.mark.asyncio
async def test_posting_rejects_another_workspaces_item(report_db):
    from erp.ledger.engine import LedgerEngine, TransactionProposal
    from erp.ledger.invariants import LedgerLineProposal

    tenant, item = uuid.uuid4(), uuid.uuid4()
    await report_db.execute(Item.__table__.insert().values(tenant_id=uuid.uuid4(), item_id=item))
    proposal = TransactionProposal(tenant_id=tenant, posting_date=date(2026, 10, 1),
        source_document_type="MANUAL_JOURNAL", source_document_id=uuid.uuid4(), entries=[
            LedgerLineProposal(account_code="1000-CASH", cost_center="MAIN", debit_amount=10,
                item_id=item, purpose="Incorrect workspace"),
            LedgerLineProposal(account_code="4000-SALES", cost_center="MAIN", credit_amount=10),
        ])
    with pytest.raises(ValueError, match="item_id must belong to this workspace"):
        await LedgerEngine().commit_transaction(report_db, proposal)
