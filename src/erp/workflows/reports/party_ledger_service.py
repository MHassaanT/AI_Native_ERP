"""Party journals calculated only from attributed receivable/payable GL legs."""
from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.ledger import Account, GeneralLedgerEntry as GL
from erp.db.models.purchasing import Supplier, SupplierInvoice
from erp.db.models.sales import Customer, SalesInvoice


class PartyLedgerService:
    @staticmethod
    def _context(party_type: str):
        if party_type == "CUSTOMER":
            return Customer, Customer.customer_id, Customer.customer_name, GL.debit_amount - GL.credit_amount
        if party_type == "SUPPLIER":
            return Supplier, Supplier.supplier_id, Supplier.supplier_name, GL.credit_amount - GL.debit_amount
        raise ValueError("Party type must be CUSTOMER or SUPPLIER.")

    @staticmethod
    def _dates(from_date: date | None, to_date: date | None):
        end = to_date or date.today()
        start = from_date or date(end.year, 1, 1)
        if start > end:
            raise ValueError("From date must not exceed to date.")
        return start, end

    async def summary(self, db: AsyncSession, tenant_id: uuid.UUID, party_type: str,
                      from_date: date | None = None, to_date: date | None = None,
                      currency: str | None = None):
        _, _, _, movement = self._context(party_type)
        start, end = self._dates(from_date, to_date)
        period = GL.posting_date >= start
        invoice_sources = (("SALES_INVOICE", "SUBSCRIPTION_INVOICE") if party_type == "CUSTOMER"
                           else ("AUTOMATED_AP_MATCH", "SUPPLIER_INVOICE", "PURCHASE_INVOICE"))
        stmt = select(
            GL.party_id, GL.currency,
            func.array_agg(aggregate_order_by(GL.party_name_snapshot, GL.posting_date.desc(), GL.created_at.desc(), GL.entry_id.desc()))[1].label("name"),
            func.sum(case((GL.posting_date < start, movement), else_=0)).label("opening"),
            func.sum(case((period, GL.debit_amount), else_=0)).label("debits"),
            func.sum(case((period, GL.credit_amount), else_=0)).label("credits"),
            func.sum(movement).label("closing"),
            func.count(func.distinct(case((period & GL.source_document_type.in_(invoice_sources), GL.source_document_id)))).label("invoice_count"),
            func.sum(case((period & GL.source_document_type.in_(invoice_sources), movement), else_=0)).label("invoiced"),
        ).where(GL.tenant_id == tenant_id, GL.party_type == party_type, GL.posting_date <= end)
        if currency:
            stmt = stmt.where(GL.currency == currency.upper())
        rows = (await db.execute(stmt.group_by(GL.party_id, GL.currency).order_by(GL.party_id, GL.currency))).all()
        return [{
            "id": str(row.party_id), "name": row.name, "currency": row.currency,
            "opening_balance": row.opening, "debit": row.debits, "credit": row.credits,
            "closing_balance": row.closing, "open_balance": row.closing,
            "invoice_count": row.invoice_count, "invoiced": row.invoiced,
            "settled_or_posted": row.invoiced - (row.debits - row.credits if party_type == "CUSTOMER" else row.credits - row.debits),
            "basis": "Attributed GL control legs; posting/matching status is never treated as payment.",
        } for row in rows]

    @staticmethod
    def _unattributed(tenant_id: uuid.UUID, end: date):
        """A conservative reconciliation list, never an inferred party balance."""
        return select(GL).outerjoin(Account, (Account.tenant_id == GL.tenant_id) &
            (Account.account_code == GL.account_code)).where(
            GL.tenant_id == tenant_id, GL.posting_date <= end, GL.party_id.is_(None),
            or_(GL.account_code.in_(("1200-AR-CUSTOMERS", "2100-AP-VENDORS", "2000-ACCOUNTS-PAYABLE")),
                func.upper(Account.account_type).in_(("RECEIVABLE", "PAYABLE"))),
        )

    async def unattributed(self, db: AsyncSession, tenant_id: uuid.UUID,
                           to_date: date | None = None, limit: int = 100, offset: int = 0):
        stmt = self._unattributed(tenant_id, to_date or date.today())
        count = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = (await db.scalars(stmt.order_by(GL.posting_date, GL.entry_id).limit(limit).offset(offset))).all()
        return {"schema_version": 2, "total_rows": count, "limit": limit, "offset": offset,
                "scope_note": "Known receivable/payable accounts only. Other legacy account roles need explicit review; no party or payment is guessed.",
                "rows": [{"entry_id": row.entry_id, "posting_date": row.posting_date,
                    "account_code": row.account_code, "currency": row.currency,
                    "debit": row.debit_amount, "credit": row.credit_amount,
                    "source_document_type": row.source_document_type, "source_document_id": row.source_document_id,
                    "attribution": "UNATTRIBUTED", "source_url": f"/ledger?transaction_id={row.transaction_id}"}
                    for row in rows]}

    async def journal(self, db: AsyncSession, tenant_id: uuid.UUID, party_type: str, party_id: uuid.UUID,
                      from_date: date | None = None, to_date: date | None = None,
                      currency: str | None = None, limit: int = 100, offset: int = 0):
        model, pk, label, movement = self._context(party_type)
        start, end = self._dates(from_date, to_date)
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("Journal page size must be 1–1000 and offset non-negative.")
        name = await db.scalar(select(label).where(model.tenant_id == tenant_id, pk == party_id))
        if name is None:
            raise LookupError("Party not found in this workspace.")
        filters = [GL.tenant_id == tenant_id, GL.party_type == party_type,
                   GL.party_id == party_id, GL.posting_date <= end]
        if currency:
            filters.append(GL.currency == currency.upper())
        order = (GL.posting_date, GL.created_at, GL.entry_id)
        history = select(
            GL.entry_id, GL.transaction_id, GL.posting_date, GL.created_at, GL.currency,
            GL.account_code, GL.party_name_snapshot, GL.debit_amount, GL.credit_amount,
            GL.source_document_type, GL.source_document_id, GL.against_document_type, GL.against_document_id,
            func.sum(movement).over(partition_by=GL.currency, order_by=order, rows=(None, 0)).label("running_balance"),
        ).where(*filters).subquery()
        stmt = select(history).where(history.c.posting_date >= start).order_by(
            history.c.posting_date, history.c.created_at, history.c.entry_id)
        count = await db.scalar(select(func.count()).select_from(history).where(history.c.posting_date >= start))
        totals = (await db.execute(select(
            GL.currency,
            func.sum(case((GL.posting_date < start, movement), else_=0)).label("opening_balance"),
            func.sum(case((GL.posting_date >= start, GL.debit_amount), else_=0)).label("debit"),
            func.sum(case((GL.posting_date >= start, GL.credit_amount), else_=0)).label("credit"),
            func.sum(movement).label("closing_balance"),
        ).where(*filters).group_by(GL.currency).order_by(GL.currency))).mappings().all()
        entries = (await db.execute(stmt.limit(limit).offset(offset))).mappings().all()
        rows = [{**dict(row), "source_url": f"/ledger?transaction_id={row['transaction_id']}"} for row in entries]
        # Outstanding amounts and ageing are based on explicit invoice settlement
        # references. Unallocated adjustments remain visible in the journal.
        invoice_model = SalesInvoice if party_type == "CUSTOMER" else SupplierInvoice
        against_type = "SALES_INVOICE" if party_type == "CUSTOMER" else "SUPPLIER_INVOICE"
        balances = select(
            GL.against_document_id.label("invoice_id"), GL.currency,
            func.sum(movement).label("outstanding"),
        ).where(*filters, GL.against_document_type == against_type).group_by(GL.against_document_id, GL.currency).subquery()
        ageing = (await db.execute(select(
            invoice_model.invoice_id, invoice_model.invoice_number, invoice_model.due_date,
            balances.c.currency, balances.c.outstanding,
        ).join(balances, (balances.c.invoice_id == invoice_model.invoice_id) & (balances.c.currency == invoice_model.currency))
          .where(invoice_model.tenant_id == tenant_id, balances.c.outstanding != 0)
          .order_by(invoice_model.due_date, invoice_model.invoice_id))).mappings().all()
        unlinked_count = await db.scalar(select(func.count()).select_from(self._unattributed(tenant_id, end).subquery()))
        unallocated = (await db.execute(select(GL.currency, func.sum(movement).label("balance"))
            .where(*filters, GL.against_document_id.is_(None)).group_by(GL.currency))).mappings().all()
        return {
            "schema_version": 2, "party_type": party_type, "party_id": party_id, "party_name": name,
            "from_date": start, "to_date": end,
            "balance_convention": "Debit minus credit" if party_type == "CUSTOMER" else "Credit minus debit",
            "totals_by_currency": [dict(row) for row in totals], "rows": rows,
            "total_rows": count, "limit": limit, "offset": offset,
            "workspace_unattributed_control_entry_count": unlinked_count,
            "unallocated_balances_by_currency": [dict(row) for row in unallocated],
            "outstanding_invoices": [{**dict(row), "overdue_days": max(0, (end - row['due_date']).days) if row['due_date'] else None} for row in ageing],
            "legacy_note": "Only attributed GL legs are included. Unlinked legacy entries require explicit reconciliation; invoice status is not payment evidence.",
        }


party_ledger_service = PartyLedgerService()
