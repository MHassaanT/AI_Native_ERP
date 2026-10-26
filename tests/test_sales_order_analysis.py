from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from erp.workflows.reports.enterprise_reports_service import EnterpriseReportsService


def test_sales_order_line_progress_uses_persisted_counters_and_amount():
    line = SimpleNamespace(
        quantity=Decimal("10"), delivered_quantity=Decimal("6"),
        invoiced_quantity=Decimal("4"), returned_quantity=Decimal("1"),
        line_total=Decimal("80"),
    )

    progress = EnterpriseReportsService._sales_order_line_progress(line, "PARTIALLY_DELIVERED")

    assert progress == {
        "ordered_quantity": Decimal("10"),
        "delivered_quantity": Decimal("6"),
        "invoiced_quantity": Decimal("4"),
        "returned_quantity": Decimal("1"),
        "pending_delivery_quantity": Decimal("4"),
        "pending_billing_quantity": Decimal("2"),
        "pending_delivery_amount": Decimal("32.0000"),
        "pending_billing_amount": Decimal("16.0000"),
    }


def test_cancelled_sales_order_has_no_pending_actions():
    line = SimpleNamespace(
        quantity=Decimal("5"), delivered_quantity=Decimal("1"),
        invoiced_quantity=Decimal("1"), returned_quantity=Decimal("0"),
        line_total=Decimal("50"),
    )

    progress = EnterpriseReportsService._sales_order_line_progress(line, "CANCELLED")

    assert progress["pending_delivery_quantity"] == 0
    assert progress["pending_billing_quantity"] == 0
    assert progress["pending_delivery_amount"] == 0
    assert progress["pending_billing_amount"] == 0


class _Rows:
    def all(self):
        return []


class _CaptureSession:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Rows()


@pytest.mark.asyncio
async def test_sales_order_analysis_query_is_line_level_and_tenant_scoped():
    tenant_id = uuid.uuid4()
    session = _CaptureSession()

    result = await EnterpriseReportsService().run(
        "sales-order-analysis", session, tenant_id,
        from_date=date(2025, 1, 1), to_date=date(2025, 12, 31),
    )

    query = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert result["rows"] == []
    assert result["basis"].startswith("Persisted sales-order-line")
    assert "sales_order_items" in query
    assert "tenant_id" in query
    assert "2025-01-01" in query and "2025-12-31" in query
