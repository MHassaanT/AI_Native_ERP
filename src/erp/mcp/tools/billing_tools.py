"""Phase 1 Billing, POS, and Budgeting MCP Tools."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.workflows.billing.budget_service import BudgetService
from erp.workflows.billing.dunning_service import DunningService
from erp.workflows.billing.pos_service import POSService
from erp.workflows.billing.subscription_service import SubscriptionService

pos_service = POSService()
budget_service = BudgetService()
dunning_service = DunningService()
subscription_service = SubscriptionService()


async def tool_stage_pos_checkout(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP Tool: Processes a point of sale transaction."""
    opening_id = uuid.UUID(str(arguments["opening_id"]))
    customer_id = uuid.UUID(str(arguments["customer_id"]))
    items = arguments["items"]
    payment_method = arguments.get("payment_method", "CASH")
    paid_amount = Decimal(str(arguments["paid_amount"])) if "paid_amount" in arguments else None

    invoice, gl_tx_id = await pos_service.process_pos_sale(
        session=session,
        tenant_id=tenant_id,
        opening_id=opening_id,
        customer_id=customer_id,
        items=items,
        payment_method=payment_method,
        paid_amount=paid_amount,
    )
    return {
        "pos_invoice_id": str(invoice.pos_invoice_id),
        "pos_invoice_number": invoice.pos_invoice_number,
        "grand_total": float(invoice.grand_total),
        "gl_transaction_id": str(gl_tx_id) if gl_tx_id else None,
    }


async def tool_evaluate_budget_compliance(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP Tool: Evaluates whether an expenditure complies with the budget."""
    return await budget_service.evaluate_budget_compliance(
        session=session,
        tenant_id=tenant_id,
        fiscal_year=int(arguments["fiscal_year"]),
        cost_center=str(arguments["cost_center"]),
        account_code=str(arguments["account_code"]),
        proposed_expense=Decimal(str(arguments["proposed_expense"])),
    )


async def tool_issue_dunning_notices(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP Tool: Scans overdue receivables and issues formal dunning notices."""
    notices = await dunning_service.evaluate_overdue_invoices(
        session=session,
        tenant_id=tenant_id,
    )
    return {"issued_count": len(notices), "notices": notices}


async def tool_trigger_subscription_billing(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP Tool: Triggers recurring subscription invoice generation."""
    invoices = await subscription_service.process_recurring_billing(
        session=session,
        tenant_id=tenant_id,
    )
    return {"processed_count": len(invoices), "invoices": invoices}
