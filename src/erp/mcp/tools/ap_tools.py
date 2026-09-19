"""Accounts Payable MCP Tool Bindings."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.workflows.accounts_payable.three_way_matcher import three_way_matcher


async def tool_execute_three_way_match(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for executing automated 3-way matching across invoice, PO, and GRN."""
    invoice_id = uuid.UUID(arguments["invoice_id"])
    po_id = uuid.UUID(arguments["po_id"])
    grn_id = uuid.UUID(arguments["grn_id"])

    result = await three_way_matcher.match_invoice(
        session=session,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        po_id=po_id,
        grn_id=grn_id,
    )
    return result.model_dump(mode="json")
