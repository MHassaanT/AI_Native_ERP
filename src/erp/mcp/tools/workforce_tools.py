"""Workforce Management MCP Tool Bindings."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.workforce.expense_auditor import ExpenseAuditRequest, expense_auditor
from erp.workforce.shift_swapper import ShiftTradeRequest, shift_coordinator


async def tool_execute_shift_trade(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for evaluating and committing peer-to-peer shift trades under labor regulations."""
    req = ShiftTradeRequest(
        requesting_employee=arguments["requesting_employee"],
        target_employee=arguments["target_employee"],
        shift_role=arguments.get("shift_role", "OPERATOR"),
        required_certification=arguments.get("required_certification"),
        target_previous_shift_end=datetime.fromisoformat(arguments["target_previous_shift_end"]),
        target_proposed_shift_start=datetime.fromisoformat(
            arguments["target_proposed_shift_start"]
        ),
        target_current_weekly_hours=float(arguments.get("target_current_weekly_hours", 32.0)),
        shift_duration_hours=float(arguments.get("shift_duration_hours", 8.0)),
    )
    result = shift_coordinator.evaluate_and_execute_trade(req)
    return result.model_dump(mode="json")


async def tool_authorize_expense_payout(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for auditing expense claims and triggering autonomous AP payout under $500."""
    claim = ExpenseAuditRequest(
        employee_code=arguments["employee_code"],
        expense_category=arguments["expense_category"],
        claim_date=date.fromisoformat(arguments.get("claim_date", date.today().isoformat())),
        total_amount=Decimal(str(arguments["total_amount"])),
        contains_alcohol=arguments.get("contains_alcohol", False),
        receipt_text=arguments.get("receipt_text", ""),
    )
    result = await expense_auditor.audit_and_reimburse(
        session=session, tenant_id=tenant_id, claim=claim
    )
    return result.model_dump(mode="json")
