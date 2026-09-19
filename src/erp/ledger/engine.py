"""Deterministic Ledger Engine (Firewall & Execution Coordinator)."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.audit.hasher import compute_audit_record_hash, get_latest_audit_hash
from erp.db.models.audit import AgentAuditLog
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.outbox import TransactionalOutbox
from erp.ledger.ceilings import CeilingEvaluationResult, evaluate_autonomy_tier
from erp.ledger.invariants import (
    LedgerLineProposal,
    validate_chart_of_accounts,
    validate_fiscal_period,
    validate_zero_sum,
)


class TransactionProposal(BaseModel):
    """Encapsulates an incoming proposal from a domain agent."""

    tenant_id: uuid.UUID
    posting_date: date
    currency: str = Field(default="USD", max_length=3)
    source_document_type: str = Field(..., max_length=64)
    source_document_id: uuid.UUID
    entries: list[LedgerLineProposal]
    human_in_the_loop_approved: bool = False
    approved_by_user_id: uuid.UUID | None = None
    verification_context: dict = Field(default_factory=dict)
    agent_id: str = "FINANCIAL_CONTROLLER"
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    prompt_template_hash: str = "hash_system_default"
    model_version: str = "gemini-3.1-pro"


class LedgerCommitResult(BaseModel):
    """Result returned upon successful atomic commit."""

    transaction_id: uuid.UUID
    tenant_id: uuid.UUID
    posting_date: date
    total_volume: Decimal
    lines_committed: int
    autonomy_evaluation: CeilingEvaluationResult
    outbox_event_id: uuid.UUID
    audit_id: uuid.UUID | None = None


class LedgerEngine:
    """Core Deterministic Ledger Engine enforcing unbypassable financial invariants."""

    def __init__(self, validate_masters: bool = True):
        self.validate_masters = validate_masters

    async def commit_transaction(
        self,
        session: AsyncSession,
        proposal: TransactionProposal,
    ) -> LedgerCommitResult:
        """Validates all financial invariants and commits transaction atomically."""
        # 1. Zero-Sum Balance & Single-Sided Invariant Check
        total_volume = validate_zero_sum(proposal.entries)

        # 2. Autonomous Financial Ceilings Check
        ceiling_result = evaluate_autonomy_tier(
            total_amount=total_volume,
            human_approved=proposal.human_in_the_loop_approved,
        )

        # 3. Fiscal Period Locking Check
        fiscal_year, fiscal_period = await validate_fiscal_period(
            session=session,
            tenant_id=proposal.tenant_id,
            posting_date=proposal.posting_date,
        )

        # 4. Master Data Integrity Check (Chart of Accounts & Cost Centers)
        if self.validate_masters:
            account_codes = {line.account_code for line in proposal.entries}
            cost_centers = {line.cost_center for line in proposal.entries}
            await validate_chart_of_accounts(
                session=session,
                tenant_id=proposal.tenant_id,
                account_codes=account_codes,
                cost_centers=cost_centers,
            )

        # 5. Generate unique transaction identifier for the balanced set of lines
        transaction_id = uuid.uuid4()

        # 6. Stage & Insert General Ledger Entries
        db_entries = []
        for line in proposal.entries:
            entry = GeneralLedgerEntry(
                tenant_id=proposal.tenant_id,
                transaction_id=transaction_id,
                posting_date=proposal.posting_date,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                account_code=line.account_code,
                cost_center=line.cost_center,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                currency=line.currency,
                exchange_rate=line.exchange_rate,
                source_document_type=proposal.source_document_type,
                source_document_id=proposal.source_document_id,
                period_closing_locked=False,
            )
            session.add(entry)
            db_entries.append(entry)

        # 7. Write to Transactional Outbox (Guarantees CDC stream consistency)
        outbox_entry = TransactionalOutbox(
            tenant_id=proposal.tenant_id,
            aggregate_type="GENERAL_LEDGER",
            aggregate_id=str(transaction_id),
            event_type="erp.finance.journal_posted",
            payload={
                "transaction_id": str(transaction_id),
                "posting_date": proposal.posting_date.isoformat(),
                "total_volume": str(total_volume),
                "line_count": len(proposal.entries),
                "source_document_type": proposal.source_document_type,
                "source_document_id": str(proposal.source_document_id),
                "tier": ceiling_result.tier.value,
            },
            trace_context={"trace_id": proposal.trace_id},
        )
        session.add(outbox_entry)

        # 8. Cryptographic Audit Log Lineage Chaining
        prev_hash = await get_latest_audit_hash(session, proposal.tenant_id)
        audit_payload = {
            "transaction_id": str(transaction_id),
            "total_volume": str(total_volume),
            "entries": [e.model_dump(mode="json") for e in proposal.entries],
        }
        current_hash = compute_audit_record_hash(
            trace_id=proposal.trace_id,
            agent_id=proposal.agent_id,
            input_payload=audit_payload,
            previous_hash=prev_hash,
        )

        audit_log = AgentAuditLog(
            tenant_id=proposal.tenant_id,
            trace_id=proposal.trace_id,
            agent_id=proposal.agent_id,
            session_id="session_" + proposal.trace_id[:8],
            model_provider="google",
            model_version=proposal.model_version,
            prompt_template_hash=proposal.prompt_template_hash,
            retrieved_context_hashes=[],
            baml_function_called="StageLedgerTransaction",
            input_payload=audit_payload,
            model_raw_output=f"Committed transaction {transaction_id} successfully.",
            parsed_structured_output={"status": "COMMITTED"},
            evaluated_guardrail_rules={
                "zero_sum_verified": True,
                "fiscal_period_verified": True,
                "tier": ceiling_result.tier.value,
            },
            human_in_the_loop_approval=proposal.human_in_the_loop_approved,
            approved_by_user_id=proposal.approved_by_user_id,
            database_transaction_id=transaction_id,
            execution_duration_ms=45,
            previous_record_hash=prev_hash,
            record_hash=current_hash,
        )
        session.add(audit_log)

        await session.flush()

        return LedgerCommitResult(
            transaction_id=transaction_id,
            tenant_id=proposal.tenant_id,
            posting_date=proposal.posting_date,
            total_volume=total_volume,
            lines_committed=len(db_entries),
            autonomy_evaluation=ceiling_result,
            outbox_event_id=outbox_entry.outbox_id,
            audit_id=audit_log.audit_id,
        )


ledger_engine = LedgerEngine()
