from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from erp.db.models.billing import CreditNote
from erp.db.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrderItem
from erp.workflows.billing.returns_service import ReturnsService


class _Result:
    def __init__(self, rows=(), one=(Decimal("0"), Decimal("0"))):
        self.rows = list(rows)
        self.one_value = one

    def all(self):
        return self.rows

    def one(self):
        return self.one_value


class _Session:
    def __init__(self, invoice, invoice_line, order_line):
        self.invoice = invoice
        self.invoice_line = invoice_line
        self.order_line = order_line
        self.added = []
        self.executed = []

    async def scalar(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is SalesInvoice:
            return self.invoice
        if entity is SalesOrderItem:
            return self.order_line
        return None

    async def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        return _Result([self.invoice_line] if entity is SalesInvoiceItem and self.invoice_line is not None else [])

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _Result()

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        for row in self.added:
            if isinstance(row, CreditNote) and row.credit_note_id is None:
                row.credit_note_id = uuid.uuid4()


class _Ledger:
    def __init__(self):
        self.proposals = []

    async def commit_transaction(self, session, proposal):
        self.proposals.append(proposal)


@pytest.mark.asyncio
async def test_invoice_linked_return_updates_order_line_and_uses_invoice_currency_tax():
    tenant_id, customer_id = uuid.uuid4(), uuid.uuid4()
    invoice_id, invoice_line_id, order_item_id, item_id = (uuid.uuid4() for _ in range(4))
    invoice = SimpleNamespace(
        invoice_id=invoice_id, customer_id=customer_id, tenant_id=tenant_id,
        status="ISSUED", currency="EUR", subtotal=Decimal("90"), tax_amount=Decimal("18"),
    )
    invoice_line = SimpleNamespace(
        invoice_item_id=invoice_line_id, invoice_id=invoice_id, tenant_id=tenant_id,
        item_id=item_id, quantity=Decimal("5"), unit_price=Decimal("20"),
        line_total=Decimal("90"), order_item_id=order_item_id,
    )
    order_line = SimpleNamespace(
        order_item_id=order_item_id, tenant_id=tenant_id, quantity=Decimal("5"),
        invoiced_quantity=Decimal("5"), returned_quantity=Decimal("0"),
    )
    session, ledger = _Session(invoice, invoice_line, order_line), _Ledger()

    credit_note = await ReturnsService(ledger_engine=ledger).issue_credit_note(
        session, tenant_id, customer_id, "Damaged item",
        [{"item_id": item_id, "sales_invoice_item_id": invoice_line_id, "quantity": Decimal("2")}],
        invoice_id=invoice_id,
    )

    assert credit_note.currency == "EUR"
    assert credit_note.subtotal == Decimal("36.0000")
    assert credit_note.tax_amount == Decimal("7.2000")
    assert credit_note.items[0].sales_invoice_item_id == invoice_line_id
    assert order_line.returned_quantity == Decimal("2")
    assert ledger.proposals[0].currency == "EUR"


@pytest.mark.asyncio
async def test_invoice_linked_return_requires_explicit_source_line():
    tenant_id, customer_id, invoice_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    invoice = SimpleNamespace(
        invoice_id=invoice_id, customer_id=customer_id, tenant_id=tenant_id,
        status="ISSUED", currency="USD", subtotal=Decimal("10"), tax_amount=Decimal("0"),
    )
    session = _Session(invoice, None, SimpleNamespace())

    with pytest.raises(ValueError, match="identify the source sales invoice item"):
        await ReturnsService(ledger_engine=_Ledger()).issue_credit_note(
            session, tenant_id, customer_id, "Return",
            [{"item_id": uuid.uuid4(), "quantity": Decimal("1"), "unit_price": Decimal("10")}],
            invoice_id=invoice_id,
        )


@pytest.mark.asyncio
async def test_invoice_linked_return_cannot_exceed_source_line_quantity():
    tenant_id, customer_id = uuid.uuid4(), uuid.uuid4()
    invoice_id, invoice_line_id, item_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    invoice = SimpleNamespace(
        invoice_id=invoice_id, customer_id=customer_id, tenant_id=tenant_id,
        status="ISSUED", currency="USD", subtotal=Decimal("50"), tax_amount=Decimal("0"),
    )
    invoice_line = SimpleNamespace(
        invoice_item_id=invoice_line_id, invoice_id=invoice_id, tenant_id=tenant_id,
        item_id=item_id, quantity=Decimal("5"), unit_price=Decimal("10"),
        line_total=Decimal("50"), order_item_id=None,
    )
    session = _Session(invoice, invoice_line, None)

    with pytest.raises(ValueError, match="exceeds the unreturned quantity"):
        await ReturnsService(ledger_engine=_Ledger()).issue_credit_note(
            session, tenant_id, customer_id, "Excess return",
            [{"item_id": item_id, "sales_invoice_item_id": invoice_line_id, "quantity": Decimal("6")}],
            invoice_id=invoice_id,
        )
