"""Mathematical Conflict Resolution Engine (PRD §Mathematical Conflict Resolution Protocol)."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field

from erp.orchestration.state import AgentActionProposal


class PolicyPriority(IntEnum):
    """Strict non-commutative partial order over domain utility functions."""

    STATUTORY_LEGAL = 5
    FINANCIAL_SOLVENCY = 4
    CONTRACTUAL_SLA = 3
    CAPACITY_THROUGHPUT = 2
    DISCRETIONARY_COST = 1


POLICY_MAP = {
    "STATUTORY_LEGAL": PolicyPriority.STATUTORY_LEGAL,
    "FINANCIAL_SOLVENCY": PolicyPriority.FINANCIAL_SOLVENCY,
    "CONTRACTUAL_SLA": PolicyPriority.CONTRACTUAL_SLA,
    "CAPACITY_THROUGHPUT": PolicyPriority.CAPACITY_THROUGHPUT,
    "DISCRETIONARY_COST": PolicyPriority.DISCRETIONARY_COST,
}


class PreemptionSignal(BaseModel):
    """Signal transmitted to preempted subagent with boundary constraint for replanning."""

    preempted_proposal_id: str
    preempted_agent_id: str
    winning_proposal_id: str
    winning_agent_id: str
    winning_policy_class: str
    boundary_violation: str
    bounded_search_space: dict[str, Any]
    escalate_to_human: bool = False


class ArbitrationResult(BaseModel):
    """Result returned by conflict resolution arbiter."""

    has_collision: bool
    staged_proposals: list[AgentActionProposal]
    preemptions: list[PreemptionSignal] = Field(default_factory=list)
    escalations: list[AgentActionProposal] = Field(default_factory=list)


class ConflictResolutionEngine:
    """Evaluates strict partial order hierarchy to deterministically arbitrate multi-agent collisions."""

    HUMAN_ESCALATION_RISK_THRESHOLD = 0.85
    HUMAN_ESCALATION_VALUE_THRESHOLD = 50000.00

    def evaluate_priority(self, policy_name: str) -> PolicyPriority:
        """Maps policy string to strict priority rank."""
        return POLICY_MAP.get(policy_name.upper(), PolicyPriority.DISCRETIONARY_COST)

    def arbitrate(
        self,
        proposals: list[AgentActionProposal],
    ) -> ArbitrationResult:
        """Arbitrates a set of concurrent proposals against resource collisions and policy ranks."""
        if not proposals:
            return ArbitrationResult(has_collision=False, staged_proposals=[])

        # Step 1: Detect collisions across shared resources
        resource_claims: dict[str, list[AgentActionProposal]] = {}
        for prop in proposals:
            for rk in prop.resource_keys:
                resource_claims.setdefault(rk, []).append(prop)

        # Check for conflicts
        conflicted_keys = {rk: claims for rk, claims in resource_claims.items() if len(claims) > 1}

        if not conflicted_keys:
            # Check high-value/risk escalation threshold on individual proposals
            escalations = [
                p
                for p in proposals
                if p.risk_score >= self.HUMAN_ESCALATION_RISK_THRESHOLD
                or p.monetary_value >= self.HUMAN_ESCALATION_VALUE_THRESHOLD
            ]
            return ArbitrationResult(
                has_collision=False,
                staged_proposals=proposals,
                escalations=escalations,
            )

        # Step 2: Strictly resolve colliding resource claims
        staged_set: set[str] = set()
        preemptions: list[PreemptionSignal] = []
        rejected_set: set[str] = set()
        escalations: list[AgentActionProposal] = []

        for rk, claims in conflicted_keys.items():
            # Sort claimants by strict priority rank descending (highest priority first)
            # Break ties by lower risk score, then lower monetary value
            sorted_claims = sorted(
                claims,
                key=lambda p: (
                    self.evaluate_priority(p.policy_class),
                    -p.risk_score,
                ),
                reverse=True,
            )

            winner = sorted_claims[0]
            staged_set.add(winner.proposal_id)

            for loser in sorted_claims[1:]:
                if loser.proposal_id in staged_set:
                    continue
                rejected_set.add(loser.proposal_id)

                # Check if escalation boundary is crossed
                escalate = (
                    loser.risk_score >= self.HUMAN_ESCALATION_RISK_THRESHOLD
                    or loser.monetary_value >= self.HUMAN_ESCALATION_VALUE_THRESHOLD
                )
                if escalate:
                    escalations.append(loser)

                preemptions.append(
                    PreemptionSignal(
                        preempted_proposal_id=loser.proposal_id,
                        preempted_agent_id=loser.agent_id,
                        winning_proposal_id=winner.proposal_id,
                        winning_agent_id=winner.agent_id,
                        winning_policy_class=winner.policy_class,
                        boundary_violation=(
                            f"CONSTRAINT_PREEMPTION: Action from {loser.agent_id} on resource '{rk}' "
                            f"preempted by higher-priority action from {winner.agent_id} "
                            f"(Policy {winner.policy_class} > {loser.policy_class})"
                        ),
                        bounded_search_space={
                            "excluded_resource": rk,
                            "claimed_by": winner.agent_id,
                            "winner_mutation": winner.state_mutation,
                        },
                        escalate_to_human=escalate,
                    )
                )

        # Collect final staged proposals
        final_staged = [p for p in proposals if p.proposal_id not in rejected_set]

        return ArbitrationResult(
            has_collision=True,
            staged_proposals=final_staged,
            preemptions=preemptions,
            escalations=escalations,
        )


conflict_engine = ConflictResolutionEngine()
