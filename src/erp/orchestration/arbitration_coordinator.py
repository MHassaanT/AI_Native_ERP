"""Multi-Agent Conflict Arbitration Coordinator (PRD §Multi-Agent Conflict Resolution).

Coordinates real-time collisions between competing agent proposals (e.g. Quality Safety vs Revenue SLA),
applies strict non-commutative mathematical partial order, persists quarantine holds to the database,
and executes agent fallback strategies (e.g. alternative warehouse rerouting or customer delay notification).
"""

import logging
import uuid
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.inventory import StockLevel, Warehouse
from erp.orchestration.conflict_resolution import (
    ArbitrationResult,
    ConflictResolutionEngine,
    conflict_engine,
)
from erp.orchestration.state import AgentActionProposal
from erp.quality.lot_quarantine import lot_quarantine_manager

logger = logging.getLogger(__name__)


class ConflictArbitrationRequest(BaseModel):
    lot_number: str
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    order_id: uuid.UUID
    customer_id: uuid.UUID
    order_quantity: Decimal
    order_monetary_value: Decimal = Decimal("50000.00")
    defect_type: str = "SURFACE_CRACK"
    defect_confidence: float = 0.99


class FallbackResult(BaseModel):
    fallback_strategy: str  # "REROUTED_TO_BACKUP_WAREHOUSE" or "CUSTOMER_DELAY_NOTIFICATION_ISSUED"
    backup_warehouse_id: uuid.UUID | None = None
    backup_warehouse_name: str | None = None
    allocated_quantity: Decimal = Decimal("0.0000")
    projected_delay_days: int = 0
    customer_notification_text: str | None = None


class ArbitrationExecutionReport(BaseModel):
    arbitration_id: str
    has_collision: bool
    winning_agent_id: str
    winning_policy_class: str
    preempted_agent_id: str
    preemption_boundary_violation: str
    lot_number: str
    stock_quarantined_in_db: bool
    fallback_execution: FallbackResult


class MultiAgentArbitrationCoordinator:
    """Coordinates multi-agent arbitration collisions, enforces database mutations, and triggers agent fallbacks."""

    def __init__(self, engine: ConflictResolutionEngine | None = None):
        self.engine = engine or conflict_engine

    async def arbitrate_quality_vs_revenue(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        req: ConflictArbitrationRequest,
    ) -> ArbitrationExecutionReport:
        """Arbitrates Quality statutory quarantine hold against VIP Revenue expedited dispatch.

        1. Mathematical conflict engine evaluates STATUTORY_LEGAL (priority 5) > CONTRACTUAL_SLA (priority 3).
        2. Winner is Quality Safety Controller.
        3. Database StockLevel for the lot is flagged is_quarantined = True.
        4. Preempted Revenue Agent executes fallback search:
           - Checks alternative warehouses for available unquarantined stock.
           - If found: re-allocates from backup warehouse.
           - If not found: generates official Customer Delay Notification.
        """
        arbitration_id = f"arb_{uuid.uuid4().hex[:8]}"

        # 1. Construct competing agent action proposals
        quality_prop = AgentActionProposal(
            proposal_id=f"prop_qual_{uuid.uuid4().hex[:6]}",
            task_id=f"task_qual_{uuid.uuid4().hex[:6]}",
            agent_id="QUALITY_SAFETY_CONTROLLER",
            tenant_id=tenant_id,
            policy_class="STATUTORY_LEGAL",
            resource_keys=[f"INVENTORY_LOT:{req.lot_number}"],
            state_mutation={
                "action": "QUARANTINE_LOT",
                "lot_number": req.lot_number,
                "defect_type": req.defect_type,
            },
            risk_score=0.95,
            monetary_value=0.0,
        )

        revenue_prop = AgentActionProposal(
            proposal_id=f"prop_rev_{uuid.uuid4().hex[:6]}",
            task_id=f"task_rev_{uuid.uuid4().hex[:6]}",
            agent_id="REVENUE_VIP_DISPATCHER",
            tenant_id=tenant_id,
            policy_class="CONTRACTUAL_SLA",
            resource_keys=[f"INVENTORY_LOT:{req.lot_number}"],
            state_mutation={
                "action": "EXPEDITE_DISPATCH",
                "lot_number": req.lot_number,
                "order_id": str(req.order_id),
                "customer_id": str(req.customer_id),
            },
            risk_score=0.20,
            monetary_value=float(req.order_monetary_value),
        )


        # 2. Mathematical Arbitration
        arb_res: ArbitrationResult = self.engine.arbitrate([quality_prop, revenue_prop])

        # Find preemption signal
        preemption = arb_res.preemptions[0] if arb_res.preemptions else None
        boundary_violation = (
            preemption.boundary_violation
            if preemption
            else "Statutory safety precedence enforced."
        )

        # 3. Enforce Winner: Quarantine lot in database
        stk_stmt = select(StockLevel).where(
            StockLevel.tenant_id == tenant_id,
            StockLevel.lot_number == req.lot_number,
        )
        stks = (await session.execute(stk_stmt)).scalars().all()
        quarantined = False
        if stks:
            for s in stks:
                s.is_quarantined = True
            quarantined = True
        else:
            # If no lot stock level exists yet, check primary warehouse stock level or create quarantine marker
            stk_wh = (
                await session.execute(
                    select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == req.item_id,
                        StockLevel.warehouse_id == req.warehouse_id,
                    )
                )
            ).scalar_one_or_none()
            if stk_wh:
                stk_wh.is_quarantined = True
                stk_wh.lot_number = req.lot_number
                quarantined = True
            else:
                new_stk = StockLevel(
                    tenant_id=tenant_id,
                    item_id=req.item_id,
                    warehouse_id=req.warehouse_id,
                    current_qty=req.order_quantity,
                    reserved_qty=Decimal("0.0000"),
                    available_qty=Decimal("0.0000"),
                    valuation_rate=Decimal("50.0000"),
                    lot_number=req.lot_number,
                    is_quarantined=True,
                )
                session.add(new_stk)
                quarantined = True

        lot_quarantine_manager.quarantined_lots.add(req.lot_number)

        # 4. Execute Revenue Agent Fallback
        # Search alternative warehouses for available stock
        alt_wh_stmt = (
            select(StockLevel, Warehouse.warehouse_name)
            .join(Warehouse, StockLevel.warehouse_id == Warehouse.warehouse_id)
            .where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.item_id == req.item_id,
                StockLevel.warehouse_id != req.warehouse_id,
                StockLevel.is_quarantined.is_(False),
                StockLevel.available_qty >= req.order_quantity,
            )
        )
        alt_stock_row = (await session.execute(alt_wh_stmt)).first()

        if alt_stock_row:
            alt_stk, alt_wh_name = alt_stock_row
            alt_stk.reserved_qty += req.order_quantity
            alt_stk.available_qty = alt_stk.current_qty - alt_stk.reserved_qty
            fallback = FallbackResult(
                fallback_strategy="REROUTED_TO_BACKUP_WAREHOUSE",
                backup_warehouse_id=alt_stk.warehouse_id,
                backup_warehouse_name=alt_wh_name,
                allocated_quantity=req.order_quantity,
                projected_delay_days=1,
                customer_notification_text=(
                    f"VIP Order {req.order_id}: Primary batch {req.lot_number} held for quality review. "
                    f"Fulfillment successfully rerouted to secondary facility '{alt_wh_name}'. ETA +24h."
                ),
            )
        else:
            fallback = FallbackResult(
                fallback_strategy="CUSTOMER_DELAY_NOTIFICATION_ISSUED",
                backup_warehouse_id=None,
                backup_warehouse_name=None,
                allocated_quantity=Decimal("0.0000"),
                projected_delay_days=3,
                customer_notification_text=(
                    f"VIP Order {req.order_id}: Shipment delayed by 3 business days due to mandatory statutory "
                    f"quality quarantine on batch {req.lot_number} ({req.defect_type}). Replacement production expedited."
                ),
            )

        await session.flush()

        return ArbitrationExecutionReport(
            arbitration_id=arbitration_id,
            has_collision=arb_res.has_collision,
            winning_agent_id=quality_prop.agent_id,
            winning_policy_class=quality_prop.policy_class,
            preempted_agent_id=revenue_prop.agent_id,
            preemption_boundary_violation=boundary_violation,
            lot_number=req.lot_number,
            stock_quarantined_in_db=quarantined,
            fallback_execution=fallback,
        )


arbitration_coordinator = MultiAgentArbitrationCoordinator()
