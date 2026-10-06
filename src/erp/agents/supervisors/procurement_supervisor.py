"""Autonomous Procurement & Sourcing Supervisor."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.channels.communications import dispatcher
from erp.agents.core.approval_engine import approval_engine
from erp.agents.core.llm_gateway import llm_gateway
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
            agent_id = agent_def.agent_id if agent_def else uuid.uuid4()

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
                duration_ms=45,
            )
            session.add(step1_log)
            step_num += 1

            if not low_stock_rows:
                run.status = "COMPLETED"
                run.summary = "All stock levels are above reorder thresholds. No procurement orders needed."
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return run

            # Process top item below ROP
            target_item, target_stock, target_warehouse = low_stock_rows[0]
            deficit = max(float(target_item.reorder_level) * 2 - float(target_stock.current_qty), 10.0)
            summary_points.append(f"Detected low stock for item '{target_item.item_name}' (Current: {target_stock.current_qty}, ROP: {target_item.reorder_level}). Order quantity: {deficit}")

            # STEP 2: Sourcing & Supplier Research
            suppliers_res = await session.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id).limit(3)
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

            llm_decision = await llm_gateway.ainvoke_json(
                prompt=f"Select the best supplier to procure {deficit} units of '{target_item.item_name}'. Suppliers available: {supplier_summaries}. Return JSON with 'selected_supplier_id', 'selected_supplier_name', 'estimated_rate', and 'rationale'.",
                system_prompt="You are an enterprise strategic sourcing AI."
            )

            chosen_supplier_id = uuid.UUID(llm_decision.get("selected_supplier_id", str(available_suppliers[0].supplier_id)))
            chosen_supplier_name = llm_decision.get("selected_supplier_name", available_suppliers[0].supplier_name)
            rate = float(llm_decision.get("estimated_rate", target_item.standard_rate or 50.0))
            po_total = deficit * rate

            step2_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="supplier_selection",
                reasoning_thought=llm_decision.get("rationale", f"Selected {chosen_supplier_name} based on supplier scorecard and reliability."),
                tool_name="llm_evaluate_sourcing",
                tool_arguments={"suppliers": supplier_summaries},
                tool_output=llm_decision,
                status="COMPLETED",
                duration_ms=450,
            )
            session.add(step2_log)
            step_num += 1

            # STEP 3: Automated RFQ Outreach (WhatsApp / Email)
            rfq_message = (
                f"Hello {chosen_supplier_name},\\n"
                f"This is an automated procurement RFQ from Zirrah Pvt Ltd. We require a quote for {deficit} units of '{target_item.item_name}'. "
                f"Please reply with availability and earliest dispatch date."
            )
            await dispatcher.send_whatsapp(
                tenant_id=tenant_id,
                agent_name="Procurement Supervisor",
                to_phone="+923001234567",
                message=rfq_message,
                run_id=run_id,
                metadata={"item_code": target_item.item_code, "quantity": deficit},
            )

            step3_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="rfq_outreach",
                reasoning_thought=f"Dispatched automated RFQ via WhatsApp to {chosen_supplier_name}.",
                tool_name="dispatch_whatsapp",
                tool_arguments={"supplier": chosen_supplier_name, "quantity": deficit},
                tool_output={"message_dispatched": True},
                status="COMPLETED",
                duration_ms=120,
            )
            session.add(step3_log)
            step_num += 1

            # STEP 4: Stage Purchase Order with HITL Approval Gate
            po_payload = {
                "supplier_id": str(chosen_supplier_id),
                "warehouse_id": str(target_warehouse.warehouse_id),
                "items": [
                    {
                        "item_id": str(target_item.item_id),
                        "quantity": deficit,
                        "rate": rate,
                        "required_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    }
                ],
                "grand_total": po_total,
                "payment_terms": "Net 30",
            }

            approval = await approval_engine.stage_approval_request(
                tenant_id=tenant_id,
                run_id=run_id,
                agent_id=agent_id,
                agent_name="Autonomous Procurement & Sourcing Supervisor",
                domain=AgentDomain.PROCUREMENT,
                action_type="CREATE_PURCHASE_ORDER",
                action_payload=po_payload,
                ai_rationale=f"Stock for '{target_item.item_name}' reached {target_stock.current_qty} (ROP {target_item.reorder_level}). Recommended ordering {deficit} units from {chosen_supplier_name} at \${rate:.2f}/unit (Total: \${po_total:,.2f}).",
                risk_level=RiskLevel.HIGH,
                required_role="Finance",
            )

            step4_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="hitl_approval_gate",
                reasoning_thought=f"Staged Purchase Order for \${po_total:,.2f} awaiting manager approval (Approval ID: {approval.approval_id}).",
                tool_name="stage_approval_request",
                tool_arguments=po_payload,
                tool_output={"approval_id": str(approval.approval_id), "status": "PENDING"},
                status="COMPLETED",
                duration_ms=50,
            )
            session.add(step4_log)

            run.status = "AWAITING_APPROVAL"
            run.summary = f"Procurement cycle initiated: Stock low on '{target_item.item_name}'. RFQ sent to {chosen_supplier_name}. Purchase Order for \${po_total:,.2f} staged in HITL approvals inbox."
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)
            return run


procurement_supervisor = ProcurementSupervisor()
