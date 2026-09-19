"""SOC 2 Type II Cryptographic Audit Chain Validator (PRD §Immutable Audit Logging)."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.audit.hasher import GENESIS_HASH, AuditHasher
from erp.db.models.audit import AgentAuditLog

logger = logging.getLogger(__name__)


class AuditBlockVerification(BaseModel):
    block_index: int
    log_id: uuid.UUID
    agent_id: str
    trace_id: str
    previous_hash: str
    record_hash: str
    is_valid: bool
    tamper_reason: str | None = None


class SOC2ComplianceReport(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"soc2_rep_{uuid.uuid4().hex[:8]}")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_blocks_verified: int
    is_chain_unbroken: bool
    tampered_blocks_count: int
    compliance_certification: str  # CERTIFIED_COMPLIANT or NON_COMPLIANT_TAMPER_DETECTED
    merkle_root_hash: str
    verified_blocks: list[AuditBlockVerification] = Field(default_factory=list)


class SOC2Auditor:
    """Traverses append-only audit records from genesis to tip, verifying cryptographic hash continuity."""

    @staticmethod
    def verify_in_memory_chain(
        records: list[dict[str, Any]],
    ) -> SOC2ComplianceReport:
        """Verifies a sequence of audit log entries for zero tampering."""
        verified_blocks = []
        expected_prev_hash = GENESIS_HASH
        tampered_count = 0

        for idx, rec in enumerate(records):
            prev_h = rec.get("previous_hash", "")
            rec_h = rec.get("record_hash", "")
            trace_id = rec.get("trace_id", "")
            agent_id = rec.get("agent_id", "")
            payload = rec.get("payload", {})
            log_id = rec.get("log_id", uuid.uuid4())

            # Verify link to previous
            link_valid = prev_h == expected_prev_hash

            # Verify hash computation
            recomputed = AuditHasher.compute_record_hash(
                previous_hash=prev_h,
                trace_id=trace_id,
                agent_id=agent_id,
                payload=payload,
            )
            hash_valid = rec_h == recomputed

            block_ok = link_valid and hash_valid
            reason = None
            if not link_valid:
                reason = f"BROKEN_CHAIN: expected previous hash {expected_prev_hash[:12]}..., found {prev_h[:12]}..."
                tampered_count += 1
            elif not hash_valid:
                reason = f"TAMPERED_RECORD: recomputed {recomputed[:12]}... differs from stored {rec_h[:12]}..."
                tampered_count += 1

            verified_blocks.append(
                AuditBlockVerification(
                    block_index=idx,
                    log_id=log_id,
                    agent_id=agent_id,
                    trace_id=trace_id,
                    previous_hash=prev_h,
                    record_hash=rec_h,
                    is_valid=block_ok,
                    tamper_reason=reason,
                )
            )
            expected_prev_hash = rec_h

        is_compliant = tampered_count == 0 and len(records) > 0
        root_hash = expected_prev_hash if records else GENESIS_HASH

        return SOC2ComplianceReport(
            total_blocks_verified=len(records),
            is_chain_unbroken=is_compliant,
            tampered_blocks_count=tampered_count,
            compliance_certification="CERTIFIED_COMPLIANT"
            if is_compliant
            else "NON_COMPLIANT_TAMPER_DETECTED",
            merkle_root_hash=root_hash,
            verified_blocks=verified_blocks,
        )

    async def verify_database_audit_chain(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> SOC2ComplianceReport:
        """Loads all audit logs for tenant ordered by sequence and validates chain integrity."""
        stmt = (
            select(AgentAuditLog)
            .where(AgentAuditLog.tenant_id == tenant_id)
            .order_by(AgentAuditLog.timestamp.asc())
        )
        logs = (await session.execute(stmt)).scalars().all()

        records = [
            {
                "log_id": log.audit_id,
                "agent_id": log.agent_id,
                "trace_id": log.trace_id,
                "previous_hash": log.previous_record_hash or GENESIS_HASH,
                "record_hash": log.record_hash,
                "payload": log.input_payload,
            }
            for log in logs
        ]
        return self.verify_in_memory_chain(records)


soc2_auditor = SOC2Auditor()
