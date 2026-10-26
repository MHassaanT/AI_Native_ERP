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
    ("report", "tables", "lineage_label"),
    [
        ("subcontracting-materials", ("subcontracting_supplied_items", "stock_ledger_entries"), "supplied_item_id"),
        ("subcontracting-finished-goods", ("subcontracting_order_items", "subcontracting_receipt_items"), "sco_item_id"),
    ],
)
async def test_subcontracting_reports_use_explicit_tenant_scoped_lineage(report, tables, lineage_label):
    tenant_id, session = uuid.uuid4(), _CaptureSession()

    result = await EnterpriseReportsService().run(report, session, tenant_id)

    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert result["rows"] == []
    assert lineage_label in result["report_name"].lower().replace(" ", "_") or lineage_label in sql
    assert all(table in sql for table in tables)
    assert "tenant_id" in sql
