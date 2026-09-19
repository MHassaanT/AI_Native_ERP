"""Tests for SOC 2 Type II Cryptographic Audit Chain Verification and Tamper Detection."""

import uuid

from erp.audit.hasher import GENESIS_HASH, AuditHasher
from erp.mesh.soc2_auditor import SOC2Auditor


def test_soc2_audit_chain_verifies_legitimate_chain():
    """Verifies that an authentic, untampered sequence of audit blocks passes SOC 2 certification."""
    auditor = SOC2Auditor()

    records = []
    prev_h = GENESIS_HASH
    agents = [
        "CHIEF_ORCHESTRATOR",
        "SUPPLY_CHAIN",
        "PRODUCTION",
        "REVENUE",
        "COMPLIANCE",
        "FINANCIAL_CONTROLLER",
    ]

    for idx, ag in enumerate(agents):
        payload = {
            "step": idx + 1,
            "agent": ag,
            "action": f"EXECUTE_WORKFLOW_STEP_{idx + 1}",
            "amount": float((idx + 1) * 100),
        }
        trace_id = f"trace_soc2_{idx}"
        rec_h = AuditHasher.compute_record_hash(
            previous_hash=prev_h,
            trace_id=trace_id,
            agent_id=ag,
            payload=payload,
        )
        records.append(
            {
                "log_id": uuid.uuid4(),
                "agent_id": ag,
                "trace_id": trace_id,
                "previous_hash": prev_h,
                "record_hash": rec_h,
                "payload": payload,
            }
        )
        prev_h = rec_h

    report = auditor.verify_in_memory_chain(records)

    assert report.total_blocks_verified == len(agents)
    assert report.is_chain_unbroken is True
    assert report.tampered_blocks_count == 0
    assert report.compliance_certification == "CERTIFIED_COMPLIANT"
    assert report.merkle_root_hash == prev_h
    assert all(b.is_valid is True for b in report.verified_blocks)


def test_soc2_audit_chain_detects_payload_tampering():
    """Verifies that any retroactive payload mutation breaks cryptographic continuity."""
    auditor = SOC2Auditor()

    records = []
    prev_h = GENESIS_HASH
    agents = ["REVENUE", "COMPLIANCE", "FINANCIAL_CONTROLLER"]

    for idx, ag in enumerate(agents):
        payload = {"step": idx + 1, "approved_price": 500.0}
        trace_id = f"trace_soc2_{idx}"
        rec_h = AuditHasher.compute_record_hash(
            previous_hash=prev_h,
            trace_id=trace_id,
            agent_id=ag,
            payload=payload,
        )
        records.append(
            {
                "log_id": uuid.uuid4(),
                "agent_id": ag,
                "trace_id": trace_id,
                "previous_hash": prev_h,
                "record_hash": rec_h,
                "payload": payload,
            }
        )
        prev_h = rec_h

    # Introduce a malicious payload modification at block 1 (COMPLIANCE)
    tampered_records = [dict(r) for r in records]
    tampered_records[1]["payload"] = {"step": 2, "approved_price": 25.0}  # Changed from 500.0

    report = auditor.verify_in_memory_chain(tampered_records)

    assert report.is_chain_unbroken is False
    assert report.tampered_blocks_count >= 1
    assert report.compliance_certification == "NON_COMPLIANT_TAMPER_DETECTED"
    assert report.verified_blocks[1].is_valid is False
    assert "TAMPERED_RECORD" in (report.verified_blocks[1].tamper_reason or "")


def test_soc2_audit_chain_detects_broken_hash_link():
    """Verifies that inserting a fraudulent block with a forged previous_hash is caught immediately."""
    auditor = SOC2Auditor()

    records = []
    prev_h = GENESIS_HASH

    for idx in range(3):
        payload = {"step": idx}
        trace_id = f"trace_{idx}"
        rec_h = AuditHasher.compute_record_hash(
            previous_hash=prev_h,
            trace_id=trace_id,
            agent_id="AGENT_X",
            payload=payload,
        )
        records.append(
            {
                "log_id": uuid.uuid4(),
                "agent_id": "AGENT_X",
                "trace_id": trace_id,
                "previous_hash": prev_h,
                "record_hash": rec_h,
                "payload": payload,
            }
        )
        prev_h = rec_h

    # Tamper the previous_hash pointer in block 2
    records[2]["previous_hash"] = "deadbeef" * 8

    report = auditor.verify_in_memory_chain(records)
    assert report.is_chain_unbroken is False
    assert report.verified_blocks[2].is_valid is False
    assert "BROKEN_CHAIN" in (report.verified_blocks[2].tamper_reason or "")
