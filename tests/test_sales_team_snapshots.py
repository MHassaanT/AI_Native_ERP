from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from erp.workflows.commercial.sales_team_service import invoice_sales_team_snapshot


def _assignment(tenant_id, partner_id, contribution, rate=None):
    return SimpleNamespace(
        tenant_id=tenant_id,
        sales_partner_id=partner_id,
        contribution_pct=Decimal(contribution),
        commission_rate=Decimal(rate) if rate is not None else None,
    )


def test_invoice_sales_team_snapshots_current_rate_and_contributions():
    tenant_id, invoice_id, partner_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    partner = SimpleNamespace(
        tenant_id=tenant_id, sales_partner_id=partner_id,
        commission_rate=Decimal("7.5000"), is_active=True,
    )

    rows = invoice_sales_team_snapshot(
        [_assignment(tenant_id, partner_id, "100")],
        {partner_id: partner}, tenant_id, invoice_id,
    )

    assert len(rows) == 1
    assert rows[0].document_type == "SALES_INVOICE"
    assert rows[0].document_id == invoice_id
    assert rows[0].commission_rate == Decimal("7.5000")


@pytest.mark.parametrize("contribution", ["99", "101"])
def test_invoice_sales_team_requires_exact_contribution_total(contribution):
    tenant_id, invoice_id, partner_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    partner = SimpleNamespace(
        tenant_id=tenant_id, sales_partner_id=partner_id,
        commission_rate=Decimal("5"), is_active=True,
    )
    with pytest.raises(ValueError, match="exactly 100%"):
        invoice_sales_team_snapshot(
            [_assignment(tenant_id, partner_id, contribution)],
            {partner_id: partner}, tenant_id, invoice_id,
        )


def test_invoice_sales_team_rejects_inactive_or_cross_tenant_partner():
    tenant_id, invoice_id, partner_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    partner = SimpleNamespace(
        tenant_id=uuid.uuid4(), sales_partner_id=partner_id,
        commission_rate=Decimal("5"), is_active=True,
    )
    with pytest.raises(ValueError, match="active and belong"):
        invoice_sales_team_snapshot(
            [_assignment(tenant_id, partner_id, "100")],
            {partner_id: partner}, tenant_id, invoice_id,
        )
