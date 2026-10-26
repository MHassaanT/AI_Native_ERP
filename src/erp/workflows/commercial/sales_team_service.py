"""Sales-team snapshot rules for converting a sales order into an invoice."""

from decimal import Decimal
import uuid

from erp.db.models.phase_b import SalesPartner, SalesTeam


def invoice_sales_team_snapshot(
    assignments: list[SalesTeam],
    partners: dict[uuid.UUID, SalesPartner],
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
) -> list[SalesTeam]:
    """Copy assigned partners to a posted invoice with frozen commission rates."""
    if not assignments:
        return []

    contribution = sum((Decimal(str(row.contribution_pct)) for row in assignments), Decimal("0"))
    if contribution != Decimal("100"):
        raise ValueError("Sales team contributions must total exactly 100% before invoicing.")

    snapshots: list[SalesTeam] = []
    for assignment in assignments:
        partner = partners.get(assignment.sales_partner_id)
        if partner is None or partner.tenant_id != tenant_id or not partner.is_active:
            raise ValueError("Every assigned sales partner must be active and belong to this workspace.")
        rate = assignment.commission_rate
        if rate is None:
            rate = partner.commission_rate
        snapshots.append(SalesTeam(
            tenant_id=tenant_id,
            document_type="SALES_INVOICE",
            document_id=invoice_id,
            sales_partner_id=partner.sales_partner_id,
            contribution_pct=assignment.contribution_pct,
            commission_rate=rate,
        ))
    return snapshots
