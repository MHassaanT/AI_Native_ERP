"""Pytest configuration and test fixtures for AI-Native ERP."""

import asyncio
import uuid
from datetime import date
from decimal import Decimal

import pytest

from erp.ledger.engine import TransactionProposal
from erp.ledger.invariants import LedgerLineProposal

TEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return TEST_TENANT_ID


@pytest.fixture
def sample_balanced_proposal(tenant_id) -> TransactionProposal:
    """Creates a valid balanced transaction proposal."""
    return TransactionProposal(
        tenant_id=tenant_id,
        posting_date=date(2026, 11, 4),
        currency="USD",
        source_document_type="PURCHASE_INVOICE",
        source_document_id=uuid.uuid4(),
        entries=[
            LedgerLineProposal(
                account_code="1300-RAW-MATERIALS",
                cost_center="PLANT-01",
                debit_amount=Decimal("18450.0000"),
                credit_amount=Decimal("0.0000"),
            ),
            LedgerLineProposal(
                account_code="2100-AP-VENDORS",
                cost_center="CORP-FINANCE",
                debit_amount=Decimal("0.0000"),
                credit_amount=Decimal("18450.0000"),
            ),
        ],
        human_in_the_loop_approved=False,
    )
