"""Human-in-the-Loop (HITL) Governance and Approval Engine."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.agents import (
    AgentApproval,
    AgentDomain,
    ApprovalStatus,
    RiskLevel,
)
from erp.db.session import async_session_factory

logger = logging.getLogger(__name__)


class ApprovalNotFoundError(LookupError):
    """The approval does not exist within the caller's tenant."""


class ApprovalConflictError(RuntimeError):
    """The approval has already reached a terminal decision."""

# High-Risk Actions that MUST pause for human verification
HIGH_RISK_ACTION_POLICIES = {
    "CREATE_PURCHASE_ORDER": (RiskLevel.HIGH, "Finance", "Supplier financial commitment requires managerial sign-off."),
    "POST_GL_JOURNAL": (RiskLevel.CRITICAL, "Finance", "General Ledger financial mutations require controller verification."),
    "DISBURSE_PAYROLL": (RiskLevel.CRITICAL, "HR", "Bank salary disbursements require HR director approval."),
    "SCRAP_FIXED_ASSET": (RiskLevel.HIGH, "Operations", "Capital asset disposal and write-off requires executive approval."),
    "ISSUE_DUNNING_LEGAL_NOTICE": (RiskLevel.HIGH, "Finance", "Legal/dunning collection notice dispatch requires collections manager sign-off."),
    "MODIFY_CREDIT_LIMIT": (RiskLevel.HIGH, "Finance", "Customer credit exposure alteration requires credit committee sign-off."),
    "ISOLATE_WORKSTATION": (RiskLevel.HIGH, "Operations", "Physical production floor line halt requires plant supervisor sign-off."),
}
SUPPORTED_APPROVAL_ACTIONS = {
    "CREATE_PURCHASE_ORDER",
    "POST_GL_JOURNAL",
    "MODIFY_CREDIT_LIMIT",
}


class ApprovalEngine:
    """Manages risk evaluation, approval creation, and action execution upon approval."""

    def evaluate_risk(self, action_type: str, payload: Dict[str, Any]) -> Tuple[bool, RiskLevel, str, str]:
        """Determines if action requires HITL approval. Returns (needs_approval, risk_level, required_role, default_reason)."""
        if action_type in HIGH_RISK_ACTION_POLICIES:
            risk_level, role, reason = HIGH_RISK_ACTION_POLICIES[action_type]
            return True, risk_level, role, reason

        # Dollar threshold check
        amount = float(payload.get("amount", payload.get("grand_total", payload.get("total_cost", 0.0))))
        if amount >= 1000.0:
            return True, RiskLevel.HIGH, "Finance", f"Financial commitment exceeding threshold (${amount:,.2f}) requires managerial sign-off."

        return False, RiskLevel.LOW, "Operator", "Low risk operational task executed autonomously."

    async def stage_approval_request(
        self,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        agent_name: str,
        domain: AgentDomain,
        action_type: str,
        action_payload: Dict[str, Any],
        ai_rationale: str,
        risk_level: Optional[RiskLevel] = None,
        required_role: Optional[str] = None,
        agent_id: Optional[uuid.UUID] = None,
    ) -> AgentApproval:
        """Creates a pending approval in PostgreSQL and halts execution until human review."""
        if action_type not in SUPPORTED_APPROVAL_ACTIONS:
            raise ValueError(f"Approval action '{action_type}' is not enabled for execution.")
        if not risk_level or not required_role:
            _, eval_risk, eval_role, _ = self.evaluate_risk(action_type, action_payload)
            risk_level = risk_level or eval_risk
            required_role = required_role or eval_role

        async with async_session_factory() as session:
            approval = AgentApproval(
                approval_id=uuid.uuid4(),
                tenant_id=tenant_id,
                run_id=run_id,
                agent_id=agent_id,
                agent_name=agent_name,
                domain=domain,
                action_type=action_type,
                action_payload=action_payload,
                risk_level=risk_level,
                required_role=required_role,
                ai_rationale=ai_rationale,
                status=ApprovalStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            session.add(approval)
            await session.commit()
            await session.refresh(approval)
            logger.info(f"Staged HITL approval {approval.approval_id} for {action_type} (Risk: {risk_level})")
            return approval

    async def resolve_approval(
        self,
        approval_id: uuid.UUID,
        tenant_id: uuid.UUID,
        decision: ApprovalStatus,
        reviewer_id: uuid.UUID,
        reviewer_role: str,
        reviewer_notes: Optional[str] = None,
        modified_payload: Optional[Dict[str, Any]] = None,
    ) -> AgentApproval:
        """Updates approval record with human decision and executes domain action if approved."""
        async with async_session_factory() as session:
            query = (
                select(AgentApproval)
                .where(
                    AgentApproval.approval_id == approval_id,
                    AgentApproval.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            res = await session.execute(query)
            approval = res.scalar_one_or_none()
            if not approval:
                raise ApprovalNotFoundError(f"Approval {approval_id} not found.")

            if approval.status != ApprovalStatus.PENDING:
                raise ApprovalConflictError("Only pending approvals can be resolved.")
            if decision not in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED, ApprovalStatus.REJECTED):
                raise ValueError("Unsupported approval decision.")

            role_aliases = {
                "TENANT_ADMIN": {"Finance", "HR", "Operations", "Admin"},
                "CONTROLLER": {"Finance"},
                "HR_MANAGER": {"HR"},
                "PLANT_MANAGER": {"Operations"},
                "OPERATIONS_MANAGER": {"Operations"},
            }
            if approval.required_role not in role_aliases.get(reviewer_role, set()):
                raise PermissionError("Reviewer does not have the role required for this approval.")

            approval.status = decision
            approval.reviewed_by = reviewer_id
            approval.reviewer_notes = reviewer_notes
            approval.modified_payload = modified_payload
            approval.reviewed_at = datetime.now(timezone.utc)
            execution_result = None
            if decision in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED):
                approval.action_execution_status = "RUNNING"
                # Domain records, decision, and result commit in this one database
                # transaction. A rollback leaves the request pending and no action committed.
                execution_result = await self._execute_approved_action(approval, session)
                approval.action_execution_status = "SUCCEEDED"
                approval.action_execution_result = execution_result
            else:
                approval.action_execution_status = "NOT_REQUIRED"
            await session.commit()
            await session.refresh(approval)

        return approval

    async def _execute_approved_action(
        self, approval: AgentApproval, session: AsyncSession
    ) -> Dict[str, Any]:
        """Run the supported database-only approval action in the decision transaction."""
        payload = approval.modified_payload or approval.action_payload
        action = approval.action_type
        tenant_id = approval.tenant_id
        logger.info("Executing approval action %s for tenant %s", action, tenant_id)

        if action == "CREATE_PURCHASE_ORDER":
            from datetime import date
            from decimal import Decimal

            from erp.db.models.inventory import Item
            from erp.db.models.purchasing import PurchaseOrder, PurchaseOrderItem, Supplier

            supplier_id = uuid.UUID(str(payload["supplier_id"]))
            supplier = (
                await session.execute(
                    select(Supplier).where(
                        Supplier.tenant_id == tenant_id,
                        Supplier.supplier_id == supplier_id,
                        Supplier.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if supplier is None:
                raise ValueError("Approved purchase order supplier is not active in this tenant.")
            raw_items = payload.get("items")
            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("Purchase order must contain at least one item.")

            line_values = []
            for item in raw_items:
                item_id = uuid.UUID(str(item["item_id"]))
                owned_item = (
                    await session.execute(
                        select(Item.item_id).where(
                            Item.tenant_id == tenant_id,
                            Item.item_id == item_id,
                            Item.is_active.is_(True),
                            Item.is_purchase_item.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if owned_item is None:
                    raise ValueError("Purchase order contains an item outside this tenant.")
                try:
                    quantity = Decimal(str(item["quantity"]))
                    rate = Decimal(str(item["rate"]))
                except (ArithmeticError, TypeError, ValueError) as exc:
                    raise ValueError("Purchase order quantities and rates must be valid numbers.") from exc
                if not quantity.is_finite() or not rate.is_finite() or quantity <= 0 or rate < 0:
                    raise ValueError("Purchase order quantities and rates must be valid non-negative amounts.")
                line_values.append((item_id, quantity, rate, quantity * rate))

            line_total = sum((line[3] for line in line_values), Decimal("0"))
            try:
                stated_total = Decimal(str(payload["grand_total"]))
            except (ArithmeticError, TypeError, ValueError) as exc:
                raise ValueError("Purchase order total must be a valid number.") from exc
            if not stated_total.is_finite() or stated_total != line_total:
                raise ValueError("Purchase order total must equal the sum of its validated lines.")

            po = PurchaseOrder(
                tenant_id=tenant_id,
                po_number=f"PO-APR-{approval.approval_id.hex.upper()}",
                supplier_id=supplier.supplier_id,
                order_date=date.today(),
                currency=supplier.currency,
                subtotal=line_total,
                tax_amount=Decimal("0.0000"),
                total_amount=line_total,
                status="SUBMITTED",
            )
            session.add(po)
            await session.flush()
            for item_id, quantity, rate, amount in line_values:
                session.add(
                    PurchaseOrderItem(
                        tenant_id=tenant_id,
                        po_id=po.po_id,
                        item_id=item_id,
                        quantity=quantity,
                        unit_price=rate,
                        line_total=amount,
                    )
                )
            await session.flush()
            return {"status": "SUCCESS", "document_type": "PurchaseOrder", "document_id": str(po.po_id)}

        if action == "POST_GL_JOURNAL":
            from datetime import date
            from erp.ledger.engine import TransactionProposal, ledger_engine
            from erp.ledger.invariants import LedgerLineProposal

            entries = [LedgerLineProposal.model_validate(line) for line in payload["entries"]]
            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=date.fromisoformat(payload["posting_date"]),
                currency=payload.get("currency", "USD"),
                source_document_type="AGENT_APPROVAL",
                source_document_id=approval.approval_id,
                entries=entries,
                human_in_the_loop_approved=True,
                approved_by_user_id=approval.reviewed_by,
                trace_id=str(approval.approval_id),
            )
            result = await ledger_engine.commit_transaction(session, proposal)
            return {
                "status": "SUCCESS",
                "document_type": "GeneralLedgerTransaction",
                "document_id": str(result.transaction_id),
            }

        if action == "MODIFY_CREDIT_LIMIT":
            from decimal import Decimal

            from erp.db.models.sales import Customer

            customer_id = uuid.UUID(str(payload["customer_id"]))
            customer = (
                await session.execute(
                    select(Customer)
                    .where(
                        Customer.tenant_id == tenant_id,
                        Customer.customer_id == customer_id,
                        Customer.is_active.is_(True),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if customer is None:
                raise ValueError("Customer is not active in this tenant.")
            try:
                new_limit = Decimal(str(payload["new_credit_limit"]))
            except (ArithmeticError, TypeError, ValueError) as exc:
                raise ValueError("New credit limit must be a valid decimal amount.") from exc
            max_limit = Decimal("99999999999999.9999")
            if not new_limit.is_finite() or new_limit < 0 or new_limit > max_limit:
                raise ValueError("New credit limit is outside the supported range.")

            prior_limit = customer.credit_limit
            customer.credit_limit = new_limit
            await session.flush()
            return {
                "status": "SUCCESS",
                "document_type": "CustomerCreditLimitChange",
                "document_id": str(customer.customer_id),
                "previous_credit_limit": str(prior_limit),
                "new_credit_limit": str(new_limit),
            }

        raise ValueError(f"Unsupported approval action: {action}")


approval_engine = ApprovalEngine()
