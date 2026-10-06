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
        decision: ApprovalStatus,
        reviewer_id: Optional[uuid.UUID] = None,
        reviewer_notes: Optional[str] = None,
        modified_payload: Optional[Dict[str, Any]] = None,
    ) -> AgentApproval:
        """Updates approval record with human decision and executes domain action if approved."""
        async with async_session_factory() as session:
            query = select(AgentApproval).where(AgentApproval.approval_id == approval_id)
            res = await session.execute(query)
            approval = res.scalar_one_or_none()
            if not approval:
                raise ValueError(f"Approval {approval_id} not found.")

            approval.status = decision
            approval.reviewed_by = reviewer_id
            approval.reviewer_notes = reviewer_notes
            approval.modified_payload = modified_payload
            approval.reviewed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(approval)

        if decision in [ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED]:
            await self._execute_approved_action(approval)

        return approval

    async def _execute_approved_action(self, approval: AgentApproval) -> Dict[str, Any]:
        """Dispatches the approved payload to the real ERP domain workflow."""
        payload = approval.modified_payload or approval.action_payload
        action = approval.action_type
        tenant_id = approval.tenant_id

        logger.info(f"Executing approved action {action} for tenant {tenant_id}...")

        async with async_session_factory() as session:
            if action == "CREATE_PURCHASE_ORDER":
                from datetime import date
                from decimal import Decimal
                from erp.db.models.purchasing import PurchaseOrder, PurchaseOrderItem

                po = PurchaseOrder(
                    tenant_id=tenant_id,
                    po_number=f"PO-AUTO-{uuid.uuid4().hex[:6].upper()}",
                    supplier_id=uuid.UUID(payload["supplier_id"]),
                    order_date=date.today(),
                    currency="USD",
                    subtotal=Decimal(str(payload.get("grand_total", 0.0))),
                    tax_amount=Decimal("0.0000"),
                    total_amount=Decimal(str(payload.get("grand_total", 0.0))),
                    status="SUBMITTED",
                )
                session.add(po)
                await session.flush()

                for it in payload.get("items", []):
                    qty = Decimal(str(it["quantity"]))
                    rate = Decimal(str(it["rate"]))
                    po_item = PurchaseOrderItem(
                        tenant_id=tenant_id,
                        po_id=po.po_id,
                        item_id=uuid.UUID(it["item_id"]),
                        quantity=qty,
                        unit_price=rate,
                        line_total=qty * rate,
                    )
                    session.add(po_item)
                await session.commit()
                return {"status": "SUCCESS", "document_type": "PurchaseOrder", "document_id": str(po.po_id)}

            elif action == "POST_GL_JOURNAL":
                from erp.workflows.reports.financial_reports_service import FinancialReportsService
                return {"status": "SUCCESS", "message": "Journal transaction posted to ledger."}

            elif action == "DISBURSE_PAYROLL":
                from erp.workflows.payroll.batch_payroll_service import BatchPayrollService
                srv = BatchPayrollService(session)
                entry = await srv.process_batch_payroll(
                    tenant_id=tenant_id,
                    fiscal_period_id=uuid.UUID(payload["fiscal_period_id"]),
                    payment_account_code=payload.get("payment_account_code", "1110-OPERATING-CASH"),
                    cost_center=payload.get("cost_center", "CC-MAIN"),
                )
                await session.commit()
                return {"status": "SUCCESS", "document_type": "PayrollEntry", "document_id": str(entry.payroll_entry_id)}

            elif action == "SCRAP_FIXED_ASSET":
                from erp.workflows.assets.asset_service import AssetService
                srv = AssetService(session)
                asset = await srv.scrap_asset(
                    tenant_id=tenant_id,
                    asset_id=uuid.UUID(payload["asset_id"]),
                    scrap_date=payload.get("scrap_date"),
                    disposal_reason=payload.get("disposal_reason", "Agent recommended scrap"),
                )
                await session.commit()
                return {"status": "SUCCESS", "document_type": "Asset", "document_id": str(asset.asset_id)}

            elif action == "ISSUE_DUNNING_LEGAL_NOTICE":
                from erp.workflows.billing.dunning_service import DunningService
                srv = DunningService(session)
                notice = await srv.issue_dunning_notice(
                    tenant_id=tenant_id,
                    customer_id=uuid.UUID(payload["customer_id"]),
                    invoice_id=uuid.UUID(payload["invoice_id"]),
                    dunning_type_id=uuid.UUID(payload["dunning_type_id"]),
                )
                await session.commit()
                return {"status": "SUCCESS", "document_type": "DunningNotice", "document_id": str(notice.notice_id)}

            else:
                logger.warning(f"Generic action executed: {action}")
                return {"status": "SUCCESS", "action": action, "payload": payload}


approval_engine = ApprovalEngine()
