"""Unit Tests for Cryptographic Audit Hash Chaining."""

from erp.audit.hasher import (
    GENESIS_BLOCK_HASH,
    compute_audit_record_hash,
)


class TestAuditHasher:
    """Tests cryptographic tamper-evident block hashing."""

    def test_genesis_hash_computation(self):
        hash1 = compute_audit_record_hash(
            trace_id="trace_001",
            agent_id="FINANCIAL_CONTROLLER",
            input_payload={"action": "reconcile", "amount": 100},
            previous_hash=None,
        )
        assert len(hash1) == 64
        assert isinstance(hash1, str)

    def test_hash_chaining_produces_deterministic_sequence(self):
        payload_1 = {"txn": "001", "total": "500.00"}
        hash_1 = compute_audit_record_hash(
            trace_id="trace_1",
            agent_id="FINANCIAL_CONTROLLER",
            input_payload=payload_1,
            previous_hash=GENESIS_BLOCK_HASH,
        )

        payload_2 = {"txn": "002", "total": "1200.00"}
        hash_2 = compute_audit_record_hash(
            trace_id="trace_2",
            agent_id="SUPPLY_CHAIN",
            input_payload=payload_2,
            previous_hash=hash_1,
        )

        assert hash_1 != hash_2
        assert len(hash_2) == 64

    def test_tampering_invalidates_downstream_chain(self):
        payload_1 = {"txn": "001", "total": "500.00"}
        hash_1 = compute_audit_record_hash(
            trace_id="trace_1",
            agent_id="FINANCIAL_CONTROLLER",
            input_payload=payload_1,
            previous_hash=GENESIS_BLOCK_HASH,
        )

        payload_2 = {"txn": "002", "total": "1200.00"}
        hash_2_original = compute_audit_record_hash(
            trace_id="trace_2",
            agent_id="SUPPLY_CHAIN",
            input_payload=payload_2,
            previous_hash=hash_1,
        )

        # Altered payload in block 1
        tampered_payload_1 = {"txn": "001", "total": "9999.00"}
        tampered_hash_1 = compute_audit_record_hash(
            trace_id="trace_1",
            agent_id="FINANCIAL_CONTROLLER",
            input_payload=tampered_payload_1,
            previous_hash=GENESIS_BLOCK_HASH,
        )

        # Recomputed block 2 with tampered block 1 hash
        hash_2_tampered = compute_audit_record_hash(
            trace_id="trace_2",
            agent_id="SUPPLY_CHAIN",
            input_payload=payload_2,
            previous_hash=tampered_hash_1,
        )

        assert hash_1 != tampered_hash_1
        assert hash_2_original != hash_2_tampered
