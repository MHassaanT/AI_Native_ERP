"""Tests for Workforce (HR) Agent: Shift Swapping Invariants and Expense Policy Auditing."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from erp.workforce.expense_auditor import (
    ExpenseAuditor,
    ExpenseAuditRequest,
)
from erp.workforce.shift_swapper import (
    ShiftTradeCoordinator,
    ShiftTradeRequest,
)


def test_shift_swap_approves_compliant_request():
    """Verifies that shift trades with >=11h rest, <=48h hours, and valid certs are approved."""
    coordinator = ShiftTradeCoordinator()

    # Previous shift ended yesterday at 17:00
    prev_end = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
    # Proposed shift starts today at 08:00 (15 hours rest > 11 hours)
    prop_start = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)

    req = ShiftTradeRequest(
        requesting_employee="EMP-001",
        target_employee="EMP-OPERATOR-01",
        shift_role="CNC Machinist",
        required_certification="CERT-CNC-5AXIS",
        target_previous_shift_end=prev_end,
        target_proposed_shift_start=prop_start,
        target_current_weekly_hours=32.0,  # 32 + 8 = 40 <= 48
        shift_duration_hours=8.0,
    )

    result = coordinator.evaluate_and_execute_trade(req)
    assert result.is_approved is True
    assert result.is_rest_compliant is True
    assert result.is_hours_compliant is True
    assert result.is_certification_compliant is True
    assert result.rest_interval_hours == 15.0
    assert result.projected_weekly_hours == 40.0
    assert len(result.rejection_reasons) == 0


def test_shift_swap_rejects_insufficient_rest():
    """Verifies invariant: shifts with rest interval < 11 hours are strictly rejected."""
    coordinator = ShiftTradeCoordinator()

    prev_end = datetime(2026, 10, 15, 23, 0, tzinfo=UTC)
    # Starts at 06:00 next morning (7 hours rest < 11h mandatory)
    prop_start = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)

    req = ShiftTradeRequest(
        requesting_employee="EMP-001",
        target_employee="EMP-002",
        shift_role="CNC Machinist",
        required_certification="CERT-CNC-5AXIS",
        target_previous_shift_end=prev_end,
        target_proposed_shift_start=prop_start,
        target_current_weekly_hours=24.0,
        shift_duration_hours=8.0,
    )

    result = coordinator.evaluate_and_execute_trade(req)
    assert result.is_approved is False
    assert result.is_rest_compliant is False
    assert any("STATUTORY_REST_VIOLATION" in r for r in result.rejection_reasons)


def test_shift_swap_rejects_weekly_hours_over_48():
    """Verifies invariant: shift trades pushing weekly hours > 48 hours are strictly rejected."""
    coordinator = ShiftTradeCoordinator()

    prev_end = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    prop_start = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)

    req = ShiftTradeRequest(
        requesting_employee="EMP-001",
        target_employee="EMP-002",
        shift_role="Assembler",
        target_previous_shift_end=prev_end,
        target_proposed_shift_start=prop_start,
        target_current_weekly_hours=44.0,  # 44 + 8 = 52 > 48
        shift_duration_hours=8.0,
    )

    result = coordinator.evaluate_and_execute_trade(req)
    assert result.is_approved is False
    assert result.is_hours_compliant is False
    assert any("STATUTORY_OVERTIME_VIOLATION" in r for r in result.rejection_reasons)


def test_shift_swap_rejects_missing_safety_certification():
    """Verifies that operators lacking active safety certification cannot accept certified shifts."""
    coordinator = ShiftTradeCoordinator()

    prev_end = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    prop_start = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)

    # EMP-003 does not have CERT-CLEANROOM-ISO5
    req = ShiftTradeRequest(
        requesting_employee="EMP-001",
        target_employee="EMP-003",
        shift_role="Cleanroom Specialist",
        required_certification="CERT-CLEANROOM-ISO5",
        target_previous_shift_end=prev_end,
        target_proposed_shift_start=prop_start,
        target_current_weekly_hours=20.0,
        shift_duration_hours=8.0,
    )

    result = coordinator.evaluate_and_execute_trade(req)
    assert result.is_approved is False
    assert result.is_certification_compliant is False
    assert any("SAFETY_CERTIFICATION_MISSING" in r for r in result.rejection_reasons)


@pytest.mark.asyncio
async def test_expense_auditor_meal_cap_and_alcohol():
    """Verifies that meal claims > $75 or containing alcohol are rejected by policy."""
    auditor = ExpenseAuditor()
    tenant_id = uuid.uuid4()

    # Meal exceeding $75 cap
    claim_excess_meal = ExpenseAuditRequest(
        employee_code="EMP-001",
        expense_category="MEALS",
        claim_date=date.today(),
        total_amount=Decimal("94.50"),
        contains_alcohol=False,
        receipt_text="Dinner at Steakhouse: $94.50",
    )
    res_meal = await auditor.audit_and_reimburse(
        session=None, tenant_id=tenant_id, claim=claim_excess_meal
    )
    assert res_meal.is_compliant is False
    assert any("MEAL_CAP_EXCEEDED" in v for v in res_meal.policy_violations)

    # Meal containing alcohol
    claim_alcohol = ExpenseAuditRequest(
        employee_code="EMP-001",
        expense_category="MEALS",
        claim_date=date.today(),
        total_amount=Decimal("45.00"),
        contains_alcohol=True,
        receipt_text="Bistro dinner with beer: $45.00",
    )
    res_alc = await auditor.audit_and_reimburse(
        session=None, tenant_id=tenant_id, claim=claim_alcohol
    )
    assert res_alc.is_compliant is False
    assert any("POLICY_VIOLATION" in v for v in res_alc.policy_violations)


@pytest.mark.asyncio
async def test_expense_auditor_deduplication():
    """Verifies that duplicate receipts are caught by hash tracking."""
    auditor = ExpenseAuditor()
    tenant_id = uuid.uuid4()

    claim1 = ExpenseAuditRequest(
        employee_code="EMP-001",
        expense_category="SUPPLIES",
        claim_date=date.today(),
        total_amount=Decimal("120.00"),
        receipt_text="Hardware store bolts receipt #99182",
    )
    res1 = await auditor.audit_and_reimburse(session=None, tenant_id=tenant_id, claim=claim1)
    assert res1.is_compliant is True
    assert res1.is_auto_approved is True

    # Same receipt submitted again
    claim2 = ExpenseAuditRequest(
        employee_code="EMP-002",
        expense_category="SUPPLIES",
        claim_date=date.today(),
        total_amount=Decimal("120.00"),
        receipt_text="Hardware store bolts receipt #99182",
    )
    res2 = await auditor.audit_and_reimburse(session=None, tenant_id=tenant_id, claim=claim2)
    assert res2.is_compliant is False
    assert any("DUPLICATE_RECEIPT" in v for v in res2.policy_violations)
