"""Banking and Treasury MCP Tool Bindings."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.workflows.reconciliation.semantic_matcher import semantic_reconciler


async def tool_reconcile_bank_transaction(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for executing hybrid semantic + exact bank feed matching."""
    amount = Decimal(str(arguments["amount"]))
    counterparty = arguments["counterparty"]
    narrative = arguments.get("narrative", "")

    result = await semantic_reconciler.find_matching_receivable(
        session=session,
        tenant_id=tenant_id,
        amount=amount,
        counterparty=counterparty,
        narrative=narrative,
    )
    return result.model_dump(mode="json")
