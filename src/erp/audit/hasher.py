"""Cryptographic Lineage and SHA-256 Hash Chaining (PRD §Guardrails)."""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.audit import AgentAuditLog

GENESIS_BLOCK_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
GENESIS_HASH = GENESIS_BLOCK_HASH


def compute_audit_record_hash(
    trace_id: str,
    agent_id: str,
    input_payload: dict[str, Any],
    previous_hash: str | None = None,
) -> str:
    """Computes a tamper-evident SHA-256 hash chaining this record with the preceding block.

    Hash = SHA256(previous_hash + trace_id + agent_id + canonical_json(input_payload))
    """
    prev = previous_hash or GENESIS_BLOCK_HASH
    canonical_payload = json.dumps(input_payload, sort_keys=True, default=str)
    raw_str = f"{prev}:{trace_id}:{agent_id}:{canonical_payload}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


class AuditHasher:
    """Helper class providing record hash computation."""

    @staticmethod
    def compute_record_hash(
        previous_hash: str,
        trace_id: str,
        agent_id: str,
        payload: dict[str, Any],
    ) -> str:
        return compute_audit_record_hash(
            trace_id=trace_id,
            agent_id=agent_id,
            input_payload=payload,
            previous_hash=previous_hash,
        )


async def get_latest_audit_hash(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> str | None:
    """Fetches the cryptographic hash of the most recent audit entry for the tenant."""
    stmt = (
        select(AgentAuditLog.record_hash)
        .where(AgentAuditLog.tenant_id == tenant_id)
        .order_by(AgentAuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
