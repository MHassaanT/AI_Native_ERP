"""Audit Logger for recording multi-agent execution context."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.audit.hasher import compute_audit_record_hash, get_latest_audit_hash
from erp.db.models.audit import AgentAuditLog


class AuditLogger:
    """Writes tamper-evident audit records into the append-only ledger."""

    @staticmethod
    async def log_agent_action(
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trace_id: str,
        agent_id: str,
        session_id: str,
        baml_function: str,
        input_payload: dict[str, Any],
        model_raw_output: str,
        parsed_structured_output: dict[str, Any],
        evaluated_guardrail_rules: dict[str, Any],
        execution_duration_ms: int,
        model_provider: str = "google",
        model_version: str = "gemini-3.1-pro",
        prompt_template_hash: str = "default_hash",
        subagent_id: str | None = None,
        human_in_the_loop_approval: bool = False,
        approved_by_user_id: uuid.UUID | None = None,
        database_transaction_id: uuid.UUID | None = None,
    ) -> AgentAuditLog:
        """Appends a cryptographically chained audit log record."""
        prev_hash = await get_latest_audit_hash(session, tenant_id)
        record_hash = compute_audit_record_hash(
            trace_id=trace_id,
            agent_id=agent_id,
            input_payload=input_payload,
            previous_hash=prev_hash,
        )

        entry = AgentAuditLog(
            tenant_id=tenant_id,
            trace_id=trace_id,
            agent_id=agent_id,
            subagent_id=subagent_id,
            session_id=session_id,
            model_provider=model_provider,
            model_version=model_version,
            prompt_template_hash=prompt_template_hash,
            retrieved_context_hashes=[],
            baml_function_called=baml_function,
            input_payload=input_payload,
            model_raw_output=model_raw_output,
            parsed_structured_output=parsed_structured_output,
            evaluated_guardrail_rules=evaluated_guardrail_rules,
            human_in_the_loop_approval=human_in_the_loop_approval,
            approved_by_user_id=approved_by_user_id,
            database_transaction_id=database_transaction_id,
            execution_duration_ms=execution_duration_ms,
            previous_record_hash=prev_hash,
            record_hash=record_hash,
        )
        session.add(entry)
        await session.flush()
        return entry
