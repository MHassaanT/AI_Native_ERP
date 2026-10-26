"""Validate explicit party/control-leg attribution without guessing from status."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.purchasing import Supplier, SupplierInvoice
from erp.db.models.sales import Customer, SalesInvoice
from erp.ledger.invariants import LedgerLineProposal


async def validate_party_lines(
    session: AsyncSession, tenant_id: uuid.UUID, lines: list[LedgerLineProposal],
) -> dict[tuple[str, uuid.UUID], str]:
    """Resolve names from tenant-owned parties and validate settlement ownership.

    Only explicitly tagged control legs participate in party balances. Revenue,
    inventory, bank and tax counterpart legs must not inherit the party, which
    would incorrectly make every invoice's party balance zero.
    """
    names: dict[tuple[str, uuid.UUID], str] = {}
    for line in lines:
        if line.party_id is None:
            continue
        key = (line.party_type, line.party_id)
        if key not in names:
            model, pk, label = (
                (Customer, Customer.customer_id, Customer.customer_name)
                if line.party_type == "CUSTOMER"
                else (Supplier, Supplier.supplier_id, Supplier.supplier_name)
            )
            name = await session.scalar(select(label).where(model.tenant_id == tenant_id, pk == line.party_id))
            if name is None:
                raise ValueError("Ledger party must belong to this workspace.")
            names[key] = name
        if line.against_document_id:
            model, party_column = (
                (SalesInvoice, SalesInvoice.customer_id) if line.party_type == "CUSTOMER"
                else (SupplierInvoice, SupplierInvoice.supplier_id)
            )
            invoice_id = await session.scalar(select(model.invoice_id).where(
                model.tenant_id == tenant_id, model.invoice_id == line.against_document_id,
                party_column == line.party_id, model.currency == line.currency,
            ))
            if invoice_id is None:
                raise ValueError("Settlement invoice must belong to the same workspace, party and currency.")
    return names
