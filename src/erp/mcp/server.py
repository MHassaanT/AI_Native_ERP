"""Model Context Protocol (MCP) JSON-RPC 2.0 Server."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from erp.mcp.schemas import MCPRequest, MCPResponse, MCPToolDefinition
from erp.mcp.tools.ap_tools import tool_execute_three_way_match
from erp.mcp.tools.banking_tools import tool_reconcile_bank_transaction
from erp.mcp.tools.commercial_tools import (
    tool_calculate_landed_margin_price,
    tool_generate_pdf_quote,
)
from erp.mcp.tools.compliance_tools import tool_evaluate_statutory_rules
from erp.mcp.tools.ledger_tools import tool_stage_ledger_transaction
from erp.mcp.tools.production_tools import tool_isolate_workstation, tool_solve_job_shop_schedule
from erp.mcp.tools.supply_chain_tools import tool_calculate_dynamic_rop
from erp.mcp.tools.workforce_tools import tool_authorize_expense_payout, tool_execute_shift_trade

logger = logging.getLogger(__name__)

AVAILABLE_TOOLS: list[MCPToolDefinition] = [
    MCPToolDefinition(
        name="stage_ledger_transaction",
        description="Stages and commits a balanced financial journal transaction through the Deterministic Ledger Engine firewall.",
        inputSchema={
            "type": "object",
            "properties": {
                "posting_date": {"type": "string", "description": "ISO-8601 date YYYY-MM-DD"},
                "currency": {"type": "string", "default": "USD"},
                "source_document_type": {"type": "string"},
                "source_document_id": {"type": "string"},
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "account_code": {"type": "string"},
                            "cost_center": {"type": "string"},
                            "debit_amount": {"type": "number"},
                            "credit_amount": {"type": "number"},
                        },
                        "required": ["account_code", "cost_center"],
                    },
                },
            },
            "required": ["posting_date", "source_document_type", "source_document_id", "entries"],
        },
    ),
    MCPToolDefinition(
        name="execute_three_way_match",
        description="Executes automated 3-way matching across an invoice, purchase order, and goods receipt note.",
        inputSchema={
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "po_id": {"type": "string"},
                "grn_id": {"type": "string"},
            },
            "required": ["invoice_id", "po_id", "grn_id"],
        },
    ),
    MCPToolDefinition(
        name="reconcile_bank_transaction",
        description="Matches open customer receivables using hybrid exact amount and pgvector semantic cosine similarity.",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "counterparty": {"type": "string"},
                "narrative": {"type": "string"},
            },
            "required": ["amount", "counterparty"],
        },
    ),
    MCPToolDefinition(
        name="evaluate_statutory_rules",
        description="Verifies an agent's proposed action against SOX, GAAP, and RBAC policies before submission.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "action_name": {"type": "string"},
                "state_mutation": {"type": "object"},
            },
            "required": ["agent_id", "action_name"],
        },
    ),
    MCPToolDefinition(
        name="calculate_dynamic_rop",
        description="Calculates stochastic Reorder Point (ROP) with Z=2.33 (99% service level) incorporating demand and lead-time variance.",
        inputSchema={
            "type": "object",
            "properties": {
                "item_code": {"type": "string"},
                "daily_demand_mean": {"type": "number"},
                "daily_demand_std": {"type": "number"},
                "lead_time_mean_days": {"type": "number"},
                "lead_time_std_days": {"type": "number"},
            },
            "required": [
                "item_code",
                "daily_demand_mean",
                "daily_demand_std",
                "lead_time_mean_days",
                "lead_time_std_days",
            ],
        },
    ),
    MCPToolDefinition(
        name="solve_job_shop_schedule",
        description="Solves production job-shop scheduling via Google OR-Tools CP-SAT solver.",
        inputSchema={
            "type": "object",
            "properties": {
                "jobs": {"type": "array"},
                "locked_workstations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["jobs"],
        },
    ),
    MCPToolDefinition(
        name="isolate_workstation",
        description="Locks out a failed machine and instantly reschedules queued operations across alternative workstations.",
        inputSchema={
            "type": "object",
            "properties": {
                "workstation_code": {"type": "string"},
                "jobs": {"type": "array"},
            },
            "required": ["workstation_code", "jobs"],
        },
    ),
    MCPToolDefinition(
        name="execute_shift_trade",
        description="Evaluates statutory labor invariants (11h rest, 48h weekly max, safety certs) and commits shift trades.",
        inputSchema={
            "type": "object",
            "properties": {
                "requesting_employee": {"type": "string"},
                "target_employee": {"type": "string"},
                "target_previous_shift_end": {"type": "string"},
                "target_proposed_shift_start": {"type": "string"},
            },
            "required": [
                "requesting_employee",
                "target_employee",
                "target_previous_shift_end",
                "target_proposed_shift_start",
            ],
        },
    ),
    MCPToolDefinition(
        name="authorize_expense_payout",
        description="Audits expense claims against policy rules and automatically stages reimbursement under $500.",
        inputSchema={
            "type": "object",
            "properties": {
                "employee_code": {"type": "string"},
                "expense_category": {"type": "string"},
                "total_amount": {"type": "number"},
            },
            "required": ["employee_code", "expense_category", "total_amount"],
        },
    ),
    MCPToolDefinition(
        name="calculate_landed_margin_price",
        description="Calculates component landed cost and defends the 22% contribution margin floor.",
        inputSchema={
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "bom_material_cost": {"type": "number"},
            },
            "required": ["sku", "bom_material_cost"],
        },
    ),
    MCPToolDefinition(
        name="generate_pdf_quote",
        description="Compiles professional commercial PDF sales quotation document.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "sku": {"type": "string"},
                "quantity": {"type": "number"},
                "unit_price": {"type": "number"},
            },
            "required": ["customer_name", "sku", "quantity", "unit_price"],
        },
    ),
]


class MCPServer:
    """Dispatches MCP JSON-RPC 2.0 tool requests."""

    def __init__(self):
        self._tool_handlers = {
            "stage_ledger_transaction": tool_stage_ledger_transaction,
            "execute_three_way_match": tool_execute_three_way_match,
            "reconcile_bank_transaction": tool_reconcile_bank_transaction,
            "evaluate_statutory_rules": tool_evaluate_statutory_rules,
            "calculate_dynamic_rop": tool_calculate_dynamic_rop,
            "solve_job_shop_schedule": tool_solve_job_shop_schedule,
            "isolate_workstation": tool_isolate_workstation,
            "execute_shift_trade": tool_execute_shift_trade,
            "authorize_expense_payout": tool_authorize_expense_payout,
            "calculate_landed_margin_price": tool_calculate_landed_margin_price,
            "generate_pdf_quote": tool_generate_pdf_quote,
        }

    async def handle_request(
        self,
        request: MCPRequest,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> MCPResponse:
        """Processes an incoming JSON-RPC 2.0 MCP request."""
        if request.method == "tools/list":
            return MCPResponse(
                id=request.id,
                result={"tools": [t.model_dump() for t in AVAILABLE_TOOLS]},
            )

        if request.method == "tools/call":
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})

            handler = self._tool_handlers.get(tool_name)
            if not handler:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Method/Tool '{tool_name}' not found"},
                )

            try:
                data = await handler(session=session, tenant_id=tenant_id, arguments=arguments)
                return MCPResponse(
                    id=request.id,
                    result={"content": [{"type": "text", "text": str(data)}], "isError": False},
                )
            except Exception as e:
                logger.exception("Error executing MCP tool '%s': %s", tool_name, e)
                return MCPResponse(
                    id=request.id,
                    error={"code": -32000, "message": str(e)},
                )

        return MCPResponse(
            id=request.id,
            error={
                "code": -32600,
                "message": f"Invalid or unsupported MCP method '{request.method}'",
            },
        )


mcp_server = MCPServer()
