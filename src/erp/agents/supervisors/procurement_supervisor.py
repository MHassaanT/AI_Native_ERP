"""Autonomous Procurement & Sourcing Supervisor."""

import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.core.approval_engine import approval_engine
from erp.agents.core.llm_gateway import LLMConfigurationError, LLMProviderError, llm_gateway
from erp.db.models.agents import (
    AgentApproval,
    AgentDefinition,
    AgentDomain,
    AgentExecutionRun,
    AgentStepLog,
    RiskLevel,
)
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.purchasing import Supplier, SupplierQuotation
from erp.db.models.tenant import Tenant
from erp.db.session import async_session_factory
from erp.workflows.procurement.sourcing_service import SourcingService

logger = logging.getLogger(__name__)


class ProcurementSupervisor:
    """Supervises the end-to-end autonomous procurement cycle."""

    SLUG = "procurement_supervisor"

    async def execute_cycle(
        self,
        tenant_id: uuid.UUID,
        trigger_type: str = "SCHEDULED",
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionRun:
        """Executes a full autonomous procurement audit and sourcing pass."""
        start_time = datetime.now(timezone.utc)
        run_id = uuid.uuid4()
        step_num = 1
        summary_points = []

        async with async_session_factory() as session:
            # 1. Fetch agent definition
            res = await session.execute(
                select(AgentDefinition).where(
                    AgentDefinition.tenant_id == tenant_id,
                    AgentDefinition.slug == self.SLUG,
                )
            )
            agent_def = res.scalar_one_or_none()
            if not agent_def:
                raise ValueError(f"Agent definition '{self.SLUG}' is not provisioned for tenant {tenant_id}.")
            if not agent_def.is_active or agent_def.autonomy_level.value == "DISABLED":
                raise ValueError(f"Agent '{agent_def.name}' is disabled.")
            agent_id = agent_def.agent_id

            # Create execution run record
            run = AgentExecutionRun(
                run_id=run_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_name="Autonomous Procurement & Sourcing Supervisor",
                trigger_type=trigger_type,
                trigger_context=trigger_context or {},
                status="RUNNING",
                started_at=start_time,
            )
            session.add(run)
            await session.commit()

            # STEP 1: Scan for low stock items
            scan_started = time.perf_counter()
            items_query = await session.execute(
                select(Item, StockLevel, Warehouse)
                .join(StockLevel, Item.item_id == StockLevel.item_id)
                .join(Warehouse, StockLevel.warehouse_id == Warehouse.warehouse_id)
                .where(
                    Item.tenant_id == tenant_id,
                    StockLevel.current_qty <= Item.reorder_level,
                )
            )
            low_stock_rows = items_query.all()

            step1_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="scan_low_stock",
                reasoning_thought=f"Scanned {len(low_stock_rows)} items falling at or below safety reorder threshold.",
                tool_name="query_stock_levels",
                tool_arguments={"tenant_id": str(tenant_id)},
                tool_output={"items_below_rop": len(low_stock_rows)},
                status="COMPLETED",
                duration_ms=int((time.perf_counter() - scan_started) * 1000),
            )
            session.add(step1_log)
            step_num += 1

            if not low_stock_rows:
                run.status = "COMPLETED"
                run.summary = "All stock levels are above reorder thresholds. No procurement orders needed."
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return run

            # STEP 2: Sourcing & Supplier Research for every item below ROP.
            suppliers_res = await session.execute(
                select(Supplier).where(
                    Supplier.tenant_id == tenant_id,
                    Supplier.is_active.is_(True),
                ).order_by(desc(Supplier.otif_score)).limit(3)
            )
            available_suppliers = suppliers_res.scalars().all()

            if not available_suppliers:
                run.status = "FAILED"
                run.summary = "Cannot procure: No suppliers configured in tenant directory."
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return run

            # Use LLM to analyze and select supplier
            supplier_summaries = [
                {"id": str(s.supplier_id), "name": s.supplier_name, "score": float(getattr(s, "otif_score", 85.0) or 85.0)}
                for s in available_suppliers
            ]
            tenant = await session.get(Tenant, tenant_id)
            company_name = tenant.company_name if tenant else "your organization"
            staged_count = 0
            for target_item, target_stock, target_warehouse in low_stock_rows:
                deficit = max(
                    float(target_item.reorder_level) * 2 - float(target_stock.current_qty), 10.0
                )
                llm_started = time.perf_counter()
                decision_source = "LLM"
                try:
                    llm_decision = await llm_gateway.ainvoke_json(
                        prompt=f"Select the best supplier to procure {deficit} units of '{target_item.item_name}'. Suppliers available: {supplier_summaries}. Return JSON with 'selected_supplier_id', 'estimated_rate', and 'rationale'.",
                        system_prompt="You are an enterprise strategic sourcing AI.",
                    )
                except (LLMConfigurationError, LLMProviderError):
                    decision_source = "RULE_FALLBACK"
                    llm_decision = {
                        "selected_supplier_id": str(available_suppliers[0].supplier_id),
                        "estimated_rate": float(target_item.standard_rate or 50.0),
                        "rationale": "Model unavailable; selected the highest-OTIF active tenant supplier and item standard rate.",
                    }

                # Model output is only a proposal: constrain the choice to this tenant's records.
                requested_supplier_id = llm_decision.get("selected_supplier_id")
                selected_supplier = next(
                    (s for s in available_suppliers if str(s.supplier_id) == str(requested_supplier_id)),
                    available_suppliers[0],
                )
                try:
                    rate = float(llm_decision.get("estimated_rate", target_item.standard_rate or 50.0))
                except (TypeError, ValueError):
                    rate = float(target_item.standard_rate or 50.0)
                if not math.isfinite(rate) or rate <= 0:
                    rate = float(target_item.standard_rate or 50.0)
                if not math.isfinite(rate) or rate <= 0:
                    rate = 50.0
                po_total = deficit * rate
                llm_duration_ms = int((time.perf_counter() - llm_started) * 1000)

                session.add(AgentStepLog(
                    step_id=uuid.uuid4(),
                    run_id=run_id,
                    step_number=step_num,
                    node_name="supplier_selection",
                    reasoning_thought=str(llm_decision.get("rationale") or "Supplier selected from tenant-approved supplier records."),
                    tool_name="llm_evaluate_sourcing",
                    tool_arguments={"item_id": str(target_item.item_id), "suppliers": supplier_summaries},
                    tool_output={
                        "selected_supplier_id": str(selected_supplier.supplier_id),
                        "estimated_rate": rate,
                        "decision_source": decision_source,
                    },
                    status="COMPLETED",
                    duration_ms=llm_duration_ms,
                ))
                step_num += 1

                # Supplier has no configured contact fields; record a draft, not a fake delivery.
                session.add(AgentStepLog(
                    step_id=uuid.uuid4(),
                    run_id=run_id,
                    step_number=step_num,
                    node_name="rfq_outreach",
                    reasoning_thought=f"RFQ draft prepared for {selected_supplier.supplier_name}; supplier contact details are not configured.",
                    tool_name="prepare_rfq_draft",
                    tool_arguments={"supplier_id": str(selected_supplier.supplier_id), "quantity": deficit},
                    tool_output={"message_dispatched": False, "reason": "supplier_contact_not_configured", "company_name": company_name},
                    status="SKIPPED",
                    duration_ms=0,
                ))
                step_num += 1

                po_payload = {
                    "supplier_id": str(selected_supplier.supplier_id),
                    "warehouse_id": str(target_warehouse.warehouse_id),
                    "items": [{
                        "item_id": str(target_item.item_id),
                        "quantity": deficit,
                        "rate": rate,
                        "required_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    }],
                    "grand_total": po_total,
                    "payment_terms": "Net 30",
                }
                approval_started = time.perf_counter()
                approval = await approval_engine.stage_approval_request(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    agent_name="Autonomous Procurement & Sourcing Supervisor",
                    domain=AgentDomain.PROCUREMENT,
                    action_type="CREATE_PURCHASE_ORDER",
                    action_payload=po_payload,
                    ai_rationale=f"Stock for '{target_item.item_name}' reached {target_stock.current_qty} (ROP {target_item.reorder_level}). Recommended ordering {deficit} units from {selected_supplier.supplier_name} at ${rate:.2f}/unit (Total: ${po_total:,.2f}).",
                    risk_level=RiskLevel.HIGH,
                    required_role="Finance",
                )
                approval_duration_ms = int((time.perf_counter() - approval_started) * 1000)
                session.add(AgentStepLog(
                    step_id=uuid.uuid4(),
                    run_id=run_id,
                    step_number=step_num,
                    node_name="hitl_approval_gate",
                    reasoning_thought=f"Purchase order proposal for ${po_total:,.2f} is awaiting finance approval.",
                    tool_name="stage_approval_request",
                    tool_arguments=po_payload,
                    tool_output={"approval_id": str(approval.approval_id), "status": "PENDING"},
                    status="COMPLETED",
                    duration_ms=approval_duration_ms,
                ))
                step_num += 1
                staged_count += 1
                summary_points.append(
                    f"{target_item.item_name}: proposed {deficit:g} units from {selected_supplier.supplier_name} (${po_total:,.2f}); approval {approval.approval_id} pending."
                )

            run.status = "AWAITING_APPROVAL" if staged_count else "COMPLETED"
            run.summary = (
                f"Reviewed {len(low_stock_rows)} low-stock item(s) and staged {staged_count} purchase proposal(s). "
                "RFQs were prepared but not sent because supplier contact details are not configured. "
                + " ".join(summary_points)
            )
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)
            return run


procurement_supervisor = ProcurementSupervisor()
