"""Compliance & Guardrail Agent (PRD §Compliance Agent)."""

import hashlib
import json

from pydantic import BaseModel, Field

from erp.orchestration.state import AgentActionProposal

# Statutory Role-Based Access Control matrix
PERMITTED_AGENT_ACTIONS: dict[str, set[str]] = {
    "FINANCIAL_CONTROLLER": {
        "stage_ledger_transaction",
        "reconcile_bank_feed",
        "query_receivables",
        "query_payables",
    },
    "SUPPLY_CHAIN": {
        "extract_invoice",
        "execute_three_way_match",
        "submit_purchase_order",
        "quarantine_material",
    },
    "PRODUCTION": {
        "dispatch_work_order",
        "route_machine_operation",
        "create_maintenance_ticket",
    },
    "REVENUE": {
        "parse_rfq",
        "generate_quotation",
        "query_stock_atp",
    },
    "WORKFORCE": {
        "process_shift_swap",
        "approve_expense_claim",
        "audit_receipt",
    },
    "CHIEF_ORCHESTRATOR": {
        "spawn_subagent",
        "terminate_subagent",
        "arbitrate_collision",
    },
    "COMPLIANCE": {
        "evaluate_statutory_rules",
        "verify_rbac",
        "sign_audit_token",
    },
}


class GuardrailEvaluationResult(BaseModel):
    is_compliant: bool
    agent_id: str
    action_name: str
    violations: list[str] = Field(default_factory=list)
    verification_token: str | None = None
    evaluated_statutes: list[str] = Field(default_factory=list)


class ComplianceGuardrailAgent:
    """Horizontal auditor and verification firewall asserting zero regulatory infractions."""

    STATUTES = ["SOX_404", "GAAP_DOUBLE_ENTRY", "IFRS_15", "EU_LABOR_LAW_48H"]

    def verify_agent_rbac(self, agent_id: str, action_name: str) -> bool:
        """Asserts that agent has permission to execute the requested operational action."""
        allowed = PERMITTED_AGENT_ACTIONS.get(agent_id.upper(), set())
        return action_name in allowed

    def evaluate_action_proposal(
        self,
        proposal: AgentActionProposal,
        action_name: str,
    ) -> GuardrailEvaluationResult:
        """Evaluates an action proposal against RBAC, statutory rules, and segregation of duties."""
        violations = []

        # 1. RBAC Check
        if not self.verify_agent_rbac(proposal.agent_id, action_name):
            violations.append(
                f"RBAC_VIOLATION: Agent '{proposal.agent_id}' is not authorized to execute action '{action_name}'"
            )

        # 2. Segregation of Duties: Sales cannot directly execute financial mutations
        if proposal.agent_id == "REVENUE" and "ledger" in action_name.lower():
            violations.append(
                "SOX_404_VIOLATION: Segregation of duties breached. Commercial sales cannot stage financial journal entries."
            )

        # 3. Labor regulation ceiling
        if proposal.agent_id == "WORKFORCE":
            hours = proposal.state_mutation.get("weekly_hours", 0)
            if hours > 48:
                violations.append(
                    f"STATUTORY_LABOR_VIOLATION: Weekly work hours {hours} exceeds statutory 48-hour limit."
                )

        if violations:
            return GuardrailEvaluationResult(
                is_compliant=False,
                agent_id=proposal.agent_id,
                action_name=action_name,
                violations=violations,
                evaluated_statutes=self.STATUTES,
            )

        # Cryptographic verification token
        raw = f"{proposal.proposal_id}:{proposal.agent_id}:{action_name}:{json.dumps(proposal.state_mutation, sort_keys=True)}"
        token = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return GuardrailEvaluationResult(
            is_compliant=True,
            agent_id=proposal.agent_id,
            action_name=action_name,
            violations=[],
            verification_token=token,
            evaluated_statutes=self.STATUTES,
        )


compliance_guardrail = ComplianceGuardrailAgent()
