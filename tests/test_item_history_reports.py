import uuid

import pytest
from sqlalchemy.dialects import postgresql

from erp.workflows.reports.enterprise_reports_service import EnterpriseReportsService


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
@pytest.mark.parametrize(
    ("report", "party_col", "source_table"),
    [
        ("item-wise-purchase-history", "suppliers.supplier_id", "goods_receipt_note_items"),
        ("item-wise-sales-history", "customers.customer_id", "delivery_note_items"),
    ],
)
async def test_item_history_reports_are_tenant_filtered_and_lineage_based(report, party_col, source_table):
    tenant_id, item_id, party_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = _CaptureSession()
    result = await EnterpriseReportsService().run(
        report, session, tenant_id, from_date=__import__("datetime").date(2025, 1, 1),
        to_date=__import__("datetime").date(2025, 12, 31), item_id=item_id,
        party_id=party_id, currency="usd",
    )

    assert result["rows"] == []
    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "tenant_id" in sql
    assert "2025-01-01" in sql and "2025-12-31" in sql
    assert str(item_id) in sql and str(party_id) in sql
    assert party_col in sql
    assert source_table in sql
