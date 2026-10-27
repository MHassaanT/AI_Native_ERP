"""Tenant-scoped GL filtering by posting dimensions and explicit source lineage."""
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from erp.db.models.billing import (
    CreditNote,
    CreditNoteItem,
    DebitNote,
    DebitNoteItem,
    POSInvoice,
    POSInvoiceItem,
)
from erp.db.models.inventory import StockLedgerEntry
from erp.db.models.ledger import GeneralLedgerEntry as GL
from erp.db.models.purchasing import SupplierInvoice, SupplierInvoiceItem
from erp.db.models.sales import SalesInvoice, SalesInvoiceItem
from erp.db.models.subcontracting import SubcontractingOrder, SubcontractingReceipt

SALES_SOURCES = ("SALES_INVOICE", "POS_INVOICE", "POS_RETURN", "CREDIT_NOTE", "SUBSCRIPTION_INVOICE", "CUSTOMER_PAYMENT", "ADVANCE_PAYMENT_ALLOCATION")
BUYING_SOURCES = ("PURCHASE_INVOICE", "SUPPLIER_INVOICE", "AUTOMATED_AP_MATCH", "DEBIT_NOTE", "SUPPLIER_PAYMENT", "LANDED_COST_VOUCHER")


class LedgerFilters(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    account_code: str | None = None
    cost_center: str | None = None
    customer_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    contractor_id: uuid.UUID | None = None
    activity: Literal["SALES", "BUYING", "SUBCONTRACTING"] | None = None
    source_document_type: str | None = None
    warehouse_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    currency: str | None = None
    transaction_id: uuid.UUID | None = None


def source_exists(model, pk, sources, *conditions):
    return select(pk).where(
        model.tenant_id == GL.tenant_id, pk == GL.source_document_id,
        GL.source_document_type.in_(sources), *conditions,
    ).correlate(GL).exists()


def contractor_exists(contractor_id=None):
    stmt = select(SubcontractingReceipt.scr_id).join(SubcontractingOrder, and_(
        SubcontractingOrder.sco_id == SubcontractingReceipt.sco_id,
        SubcontractingOrder.tenant_id == SubcontractingReceipt.tenant_id,
    )).where(
        SubcontractingReceipt.tenant_id == GL.tenant_id,
        SubcontractingReceipt.scr_id == GL.source_document_id,
        GL.source_document_type == "SUBCONTRACTING_RECEIPT",
    )
    if contractor_id:
        stmt = stmt.where(SubcontractingOrder.supplier_id == contractor_id)
    return stmt.correlate(GL).exists()


def ledger_conditions(tenant_id, filters):
    if filters.from_date and filters.to_date and filters.from_date > filters.to_date:
        raise ValueError("From date must be on or before To date.")
    conditions = [GL.tenant_id == tenant_id]
    for field in ("account_code", "cost_center", "currency", "transaction_id", "source_document_type"):
        if value := getattr(filters, field):
            conditions.append(getattr(GL, field) == value)
    if filters.from_date:
        conditions.append(GL.posting_date >= filters.from_date)
    if filters.to_date:
        conditions.append(GL.posting_date <= filters.to_date)
    if filters.activity == "SALES":
        conditions.append(GL.source_document_type.in_(SALES_SOURCES))
    elif filters.activity == "BUYING":
        conditions.append(GL.source_document_type.in_(BUYING_SOURCES))
    elif filters.activity == "SUBCONTRACTING":
        conditions.append(GL.source_document_type.startswith("SUBCONTRACTING_"))

    # A party filter selects the complete journal, without attributing counterpart
    # lines to the party's control balance. Source links also cover legacy rows.
    for party_type, party_id in (("CUSTOMER", filters.customer_id), ("SUPPLIER", filters.supplier_id)):
        if not party_id:
            continue
        peer = aliased(GL)
        matches = [select(peer.entry_id).where(
            peer.tenant_id == GL.tenant_id, peer.transaction_id == GL.transaction_id,
            peer.party_type == party_type, peer.party_id == party_id,
        ).correlate(GL).exists()]
        specs = (
            ((SalesInvoice, SalesInvoice.invoice_id, ("SALES_INVOICE",), SalesInvoice.customer_id),
             (POSInvoice, POSInvoice.pos_invoice_id, ("POS_INVOICE", "POS_RETURN"), POSInvoice.customer_id),
             (CreditNote, CreditNote.credit_note_id, ("CREDIT_NOTE",), CreditNote.customer_id))
            if party_type == "CUSTOMER" else
            ((SupplierInvoice, SupplierInvoice.invoice_id, ("PURCHASE_INVOICE", "SUPPLIER_INVOICE", "AUTOMATED_AP_MATCH"), SupplierInvoice.supplier_id),
             (DebitNote, DebitNote.debit_note_id, ("DEBIT_NOTE",), DebitNote.supplier_id))
        )
        matches.extend(source_exists(model, pk, sources, party_column == party_id) for model, pk, sources, party_column in specs)
        if party_type == "SUPPLIER":
            matches.append(contractor_exists(party_id))
        conditions.append(or_(*matches))
    if filters.contractor_id:
        conditions.append(contractor_exists(filters.contractor_id))

    if filters.warehouse_id or filters.item_id:
        # Match both dimensions on the same stock movement, avoiding false
        # matches where an item and warehouse occur on unrelated document rows.
        stock = select(StockLedgerEntry.entry_id).where(
            StockLedgerEntry.tenant_id == GL.tenant_id,
            StockLedgerEntry.source_document_id == GL.source_document_id,
            or_(StockLedgerEntry.source_document_type == GL.source_document_type,
                and_(GL.source_document_type == "SUBCONTRACTING_RECEIPT",
                     StockLedgerEntry.source_document_type.in_(("SUBCONTRACTING_RECEIPT_FG", "SUBCONTRACTING_COMPONENT_CONSUME")))),
        )
        direct = []
        for field in ("warehouse_id", "item_id"):
            if value := getattr(filters, field):
                stock = stock.where(getattr(StockLedgerEntry, field) == value)
                direct.append(getattr(GL, field) == value)
        matches = [and_(*direct), stock.correlate(GL).exists()]
        # Sales invoices refer to stock movements through their delivery note.
        delivery_stock = select(StockLedgerEntry.entry_id).where(
            StockLedgerEntry.tenant_id == GL.tenant_id,
            StockLedgerEntry.source_document_type == "DELIVERY_NOTE",
            StockLedgerEntry.source_document_id == SalesInvoice.delivery_note_id,
        )
        for field in ("warehouse_id", "item_id"):
            if value := getattr(filters, field):
                delivery_stock = delivery_stock.where(getattr(StockLedgerEntry, field) == value)
        matches.append(source_exists(SalesInvoice, SalesInvoice.invoice_id, ("SALES_INVOICE",),
            delivery_stock.correlate(GL, SalesInvoice).exists()))
        # Supplier invoices have a different source from their goods receipt.
        if filters.warehouse_id:
            receipt_stock = select(StockLedgerEntry.entry_id).where(
                StockLedgerEntry.tenant_id == GL.tenant_id,
                StockLedgerEntry.source_document_type == "GOODS_RECEIPT",
                StockLedgerEntry.source_document_id == SupplierInvoice.grn_id,
                StockLedgerEntry.warehouse_id == filters.warehouse_id,
            )
            if filters.item_id:
                receipt_stock = receipt_stock.where(StockLedgerEntry.item_id == filters.item_id)
            matches.append(source_exists(SupplierInvoice, SupplierInvoice.invoice_id,
                ("PURCHASE_INVOICE", "SUPPLIER_INVOICE", "AUTOMATED_AP_MATCH"), receipt_stock.correlate(GL, SupplierInvoice).exists()))
        # Non-stock invoices can still be selected by their explicit item rows.
        if filters.item_id and not filters.warehouse_id:
            for model, _pk, parent, sources in (
                (SalesInvoiceItem, SalesInvoiceItem.invoice_item_id, SalesInvoiceItem.invoice_id, ("SALES_INVOICE",)),
                (SupplierInvoiceItem, SupplierInvoiceItem.invoice_item_id, SupplierInvoiceItem.invoice_id, ("PURCHASE_INVOICE", "SUPPLIER_INVOICE", "AUTOMATED_AP_MATCH")),
                (POSInvoiceItem, POSInvoiceItem.pos_item_id, POSInvoiceItem.pos_invoice_id, ("POS_INVOICE", "POS_RETURN")),
                (CreditNoteItem, CreditNoteItem.cn_item_id, CreditNoteItem.credit_note_id, ("CREDIT_NOTE",)),
                (DebitNoteItem, DebitNoteItem.dn_item_id, DebitNoteItem.debit_note_id, ("DEBIT_NOTE",)),
            ):
                matches.append(source_exists(model, parent, sources, model.item_id == filters.item_id))
        conditions.append(or_(*matches))
    return conditions


async def query_ledger(session, tenant_id, filters, limit=100, offset=0):
    conditions = ledger_conditions(tenant_id, filters)
    entries = (await session.scalars(select(GL).where(*conditions).order_by(
        GL.posting_date.desc(), GL.created_at.desc(), GL.entry_id.desc(),
    ).limit(limit).offset(offset))).all()
    total = await session.scalar(select(func.count()).select_from(GL).where(*conditions))
    totals = (await session.execute(select(GL.currency,
        func.sum(GL.debit_amount).label("debit"), func.sum(GL.credit_amount).label("credit"),
    ).where(*conditions).group_by(GL.currency).order_by(GL.currency))).mappings().all()
    # Always use the full journal for From/To, even when filtering a single leg.
    peers = []
    if entries:
        peers = (await session.scalars(select(GL).where(GL.tenant_id == tenant_id,
            GL.transaction_id.in_({e.transaction_id for e in entries})))).all()
    by_transaction = {}
    for peer in peers:
        group = by_transaction.setdefault(peer.transaction_id, {"from_accounts": set(), "to_accounts": set()})
        group["from_accounts" if peer.credit_amount > 0 else "to_accounts"].add(peer.account_code)
    return {"entries": entries, "total": total, "totals": [dict(row) for row in totals],
            "counterparts": by_transaction}
