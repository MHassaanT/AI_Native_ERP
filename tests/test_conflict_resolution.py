"""Unit Tests for 5-Level Priority Conflict Resolution Engine."""

import uuid

from erp.orchestration.conflict_resolution import (
    PolicyPriority,
    conflict_engine,
)
from erp.orchestration.state import AgentActionProposal


class TestConflictResolutionEngine:
    """Tests the mathematical non-commutative partial order conflict resolution protocol."""

    def test_priority_hierarchy_values(self):
        assert PolicyPriority.STATUTORY_LEGAL > PolicyPriority.FINANCIAL_SOLVENCY
        assert PolicyPriority.FINANCIAL_SOLVENCY > PolicyPriority.CONTRACTUAL_SLA
        assert PolicyPriority.CONTRACTUAL_SLA > PolicyPriority.CAPACITY_THROUGHPUT
        assert PolicyPriority.CAPACITY_THROUGHPUT > PolicyPriority.DISCRETIONARY_COST

    def test_emergency_rush_order_vs_machine_safety(self):
        """PRD Case: Rush VIP order (Contractual SLA) vs Machine Safety Rebuild (Statutory Legal).

        Statutory Legal MUST dominate Contractual SLA.
        """
        tenant_id = uuid.uuid4()
        workstation_resource = "workstation:WS-INJECTION-01"

        # Revenue Agent proposes rush VIP run
        action_revenue = AgentActionProposal(
            task_id="t_rush_vip",
            agent_id="REVENUE",
            tenant_id=tenant_id,
            policy_class="CONTRACTUAL_SLA",
            resource_keys=[workstation_resource],
            state_mutation={"operation": "SCHEDULE_VIP_BATCH", "duration_hours": 12},
        )

        # Production Agent flags bearing anomaly and requires immediate safety rebuild
        action_production = AgentActionProposal(
            task_id="t_maint_rebuild",
            agent_id="PRODUCTION",
            tenant_id=tenant_id,
            policy_class="STATUTORY_LEGAL",
            resource_keys=[workstation_resource],
            state_mutation={"operation": "LOCKOUT_MAINTENANCE", "fault": "VIBRATION_SPIKE"},
        )

        result = conflict_engine.arbitrate([action_revenue, action_production])

        assert result.has_collision is True
        assert len(result.staged_proposals) == 1
        assert result.staged_proposals[0].agent_id == "PRODUCTION"

        assert len(result.preemptions) == 1
        preemption = result.preemptions[0]
        assert preemption.preempted_agent_id == "REVENUE"
        assert preemption.winning_agent_id == "PRODUCTION"
        assert preemption.winning_policy_class == "STATUTORY_LEGAL"
        assert "CONSTRAINT_PREEMPTION" in preemption.boundary_violation
        assert preemption.bounded_search_space["excluded_resource"] == workstation_resource

    def test_bulk_purchase_vs_cash_liquidity_covenant(self):
        """PRD Case: Procurement bulk rebate (Discretionary Cost) vs Finance Cash Buffer (Solvency).

        Financial Solvency MUST dominate Discretionary Cost.
        """
        tenant_id = uuid.uuid4()
        cash_resource = "treasury:operating_cash_buffer"

        action_procurement = AgentActionProposal(
            task_id="t_bulk_resin",
            agent_id="SUPPLY_CHAIN",
            tenant_id=tenant_id,
            policy_class="DISCRETIONARY_COST",
            resource_keys=[cash_resource],
            state_mutation={"expenditure": 45000.0},
        )

        action_finance = AgentActionProposal(
            task_id="t_cash_covenant",
            agent_id="FINANCIAL_CONTROLLER",
            tenant_id=tenant_id,
            policy_class="FINANCIAL_SOLVENCY",
            resource_keys=[cash_resource],
            state_mutation={"lock_minimum_reserve": 250000.0},
        )

        result = conflict_engine.arbitrate([action_procurement, action_finance])

        assert result.has_collision is True
        assert len(result.staged_proposals) == 1
        assert result.staged_proposals[0].agent_id == "FINANCIAL_CONTROLLER"

        preemption = result.preemptions[0]
        assert preemption.preempted_agent_id == "SUPPLY_CHAIN"
        assert preemption.winning_agent_id == "FINANCIAL_CONTROLLER"

    def test_high_value_action_triggers_human_escalation(self):
        """Transactions exceeding $50,000 USD trigger escalation boundary."""
        tenant_id = uuid.uuid4()
        action_large = AgentActionProposal(
            task_id="t_capex",
            agent_id="FINANCIAL_CONTROLLER",
            tenant_id=tenant_id,
            policy_class="FINANCIAL_SOLVENCY",
            resource_keys=["treasury:capex"],
            state_mutation={"capex": 75000.0},
            monetary_value=75000.0,
        )

        result = conflict_engine.arbitrate([action_large])
        assert len(result.escalations) == 1
        assert result.escalations[0].monetary_value == 75000.0
