"""Ledger Engine MCP Tool Bindings."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.ledger.engine import TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal


async def tool_stage_ledger_transaction(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for staging a balanced journal mutation through the Deterministic Ledger Engine."""
    posting_date = date.fromisoformat(arguments["posting_date"])
    currency = arguments.get("currency", "USD")
    src_type = arguments["source_document_type"]
    src_id = uuid.UUID(arguments["source_document_id"])

    entries = [
        LedgerLineProposal(
            account_code=e["account_code"],
            cost_center=e["cost_center"],
            debit_amount=Decimal(str(e.get("debit_amount", 0))),
            credit_amount=Decimal(str(e.get("credit_amount", 0))),
            currency=currency,
        )
        for e in arguments["entries"]
    ]

    proposal = TransactionProposal(
        tenant_id=tenant_id,
        posting_date=posting_date,
        currency=currency,
        source_document_type=src_type,
        source_document_id=src_id,
        entries=entries,
        human_in_the_loop_approved=arguments.get("human_in_the_loop_approved", False),
        agent_id=arguments.get("agent_id", "MCP_CLIENT"),
    )

    result = await ledger_engine.commit_transaction(session=session, proposal=proposal)
    return {
        "status": "COMMITTED",
        "transaction_id": str(result.transaction_id),
        "total_volume": str(result.total_volume),
        "lines_committed": result.lines_committed,
        "autonomy_tier": result.autonomy_evaluation.tier.value,
        "outbox_event_id": str(result.outbox_event_id),
    }
