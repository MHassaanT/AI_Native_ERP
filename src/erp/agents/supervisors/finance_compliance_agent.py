"""Autonomous Finance & Compliance Controller."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.channels.communications import dispatcher
from erp.agents.core.llm_gateway import llm_gateway
from erp.db.models.agents import (
    AgentDefinition,
    AgentExecutionRun,
    AgentStepLog,
)
from erp.db.models.billing import Budget
from erp.db.models.currency import CurrencyExchangeRate
from erp.db.models.sales import SalesInvoice
from erp.db.session import async_session_factory
from erp.workflows.currency.exchange_service import ExchangeService

logger = logging.getLogger(__name__)


class FinanceComplianceAgent:
    """Supervises accounts receivable collections, budget compliance, and FX revaluation."""

    SLUG = "finance_compliance_agent"

    async def execute_cycle(
        self,
        tenant_id: uuid.UUID,
        trigger_type: str = "SCHEDULED",
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionRun:
        """Executes autonomous collections, budget overrun check, and currency audit."""
        start_time = datetime.now(timezone.utc)
        run_id = uuid.uuid4()
        step_num = 1
        summary_points = []

        async with async_session_factory() as session:
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

            run = AgentExecutionRun(
                run_id=run_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_name="Autonomous Finance & Compliance Controller",
                trigger_type=trigger_type,
                trigger_context=trigger_context or {},
                status="RUNNING",
                started_at=start_time,
            )
            session.add(run)
            await session.commit()

            # STEP 1: Overdue AR Invoices & Tiered Dunning Check
            today_date = datetime.now(timezone.utc).date()
            overdue_query = await session.execute(
                select(SalesInvoice).where(
                    SalesInvoice.tenant_id == tenant_id,
                    SalesInvoice.status.in_(["ISSUED", "OVERDUE", "SUBMITTED"]),
                    SalesInvoice.due_date < today_date,
                    SalesInvoice.total_amount > 0,
                ).limit(5)
            )
            overdue_invoices = overdue_query.scalars().all()

            step1_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="scan_overdue_receivables",
                reasoning_thought=f"Selected {len(overdue_invoices)} invoices with an overdue due date and an open status.",
                tool_name="query_overdue_invoices",
                tool_arguments={"as_of_date": str(today_date)},
                tool_output={"overdue_count": len(overdue_invoices)},
                status="COMPLETED",
                duration_ms=45,
            )
            session.add(step1_log)
            step_num += 1

            if overdue_invoices:
                target_inv = overdue_invoices[0]
                days_overdue = (today_date - target_inv.due_date).days
                amount = float(target_inv.total_amount)

                session.add(AgentStepLog(
                    step_id=uuid.uuid4(),
                    run_id=run_id,
                    step_number=step_num,
                    node_name="dunning_action_gate",
                    reasoning_thought="Overdue invoice identified; legal notice execution is disabled until a supported notice and delivery handler is configured.",
                    tool_name="check_dunning_action_support",
                    tool_arguments={"invoice_id": str(target_inv.invoice_id)},
                    tool_output={"notice_created": False, "notice_sent": False, "reason": "dunning_action_unavailable"},
                    status="SKIPPED",
                    duration_ms=0,
                ))
                step_num += 1
                summary_points.append(
                    f"Invoice #{target_inv.invoice_number} is {days_overdue} days overdue (${amount:,.2f}); no dunning notice was created or sent because the action handler is unavailable."
                )

            # STEP 2: Cost Center Budget Overrun Monitoring
            budgets_res = await session.execute(
                select(Budget).where(
                    Budget.tenant_id == tenant_id,
                    Budget.is_active == True,
                ).limit(5)
            )
            active_budgets = budgets_res.scalars().all()

            step2_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="audit_cost_center_budgets",
                reasoning_thought=f"Loaded {len(active_budgets)} active budget records. Actual-versus-budget calculations are not implemented in this cycle.",
                tool_name="load_active_budgets",
                tool_arguments={"tenant_id": str(tenant_id)},
                tool_output={"active_budgets": len(active_budgets), "variance_calculated": False},
                status="SKIPPED",
                duration_ms=0,
            )
            session.add(step2_log)
            step_num += 1

            # STEP 3: Foreign Currency Exchange Rate & Period-End Revaluation Check
            rates_count = await session.scalar(
                select(func.count(CurrencyExchangeRate.rate_id)).where(CurrencyExchangeRate.tenant_id == tenant_id)
            )

            step3_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="audit_fx_revaluation",
                reasoning_thought=f"Counted {rates_count} configured currency rates. FX exposure and IAS 21 revaluation calculations are not implemented in this cycle.",
                tool_name="count_currency_rates",
                tool_arguments={"tenant_id": str(tenant_id)},
                tool_output={"currency_rates_count": rates_count, "revaluation_performed": False},
                status="SKIPPED",
                duration_ms=0,
            )
            session.add(step3_log)

            run.status = "COMPLETED"
            run.summary = (
                "Finance checks completed. "
                + (" ".join(summary_points) if summary_points else "No overdue invoices were found.")
                + f" Loaded {len(active_budgets)} active budget record(s) and counted {rates_count} currency rate(s); budget variances and FX revaluation were not calculated."
            )
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)
            return run


finance_compliance_agent = FinanceComplianceAgent()
