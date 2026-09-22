"""Asynchronous DAG Execution Engine and Background Task Worker."""

import asyncio
from datetime import UTC, datetime
import logging
from decimal import Decimal
from typing import Any

from erp.baml_client.client import baml_client
from erp.commercial.pricing_engine import pricing_engine
from erp.orchestration.dag import TaskDAG, TaskNode, TaskStatus
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.state import AgentState
from erp.production.cpsat_scheduler import JobOperationSpec, JobSpec, cpsat_scheduler

logger = logging.getLogger(__name__)


class DAGExecutor:
    """Executes hierarchical task DAGs across autonomous domain subagents."""

    async def execute_dag(self, dag: TaskDAG) -> dict[str, Any]:
        """Runs all DAG nodes to completion based on topological readiness."""
        logger.info("Starting execution of DAG %s (%d nodes)", dag.dag_id, len(dag.nodes))

        context_accumulator: dict[str, Any] = {}

        while not dag.is_finished():
            ready_nodes = dag.get_ready_tasks()
            if not ready_nodes:
                # If there are no ready nodes but DAG is not finished, check if there's deadlock or failure
                pending = [n for n in dag.nodes.values() if n.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
                if not pending:
                    break
                await asyncio.sleep(0.05)
                continue

            tasks = [self._execute_node(node, context_accumulator) for node in ready_nodes]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, res in zip(ready_nodes, results, strict=False):
                if isinstance(res, Exception):
                    logger.error("Node %s failed: %s", node.name, res)
                    dag.mark_failed(node.task_id, str(res))
                else:
                    dag.mark_completed(node.task_id, res or {})
                    context_accumulator[node.task_id] = res
                    if isinstance(res, dict):
                        context_accumulator.update(res)

        logger.info("DAG %s execution completed.", dag.dag_id)
        return context_accumulator

    async def _execute_node(self, node: TaskNode, ctx: dict[str, Any]) -> dict[str, Any]:
        """Dispatches subtask execution according to agent_id and task name."""
        node.status = TaskStatus.RUNNING
        node.started_at = datetime.now(UTC)
        chief_orchestrator.agent_states[node.agent_id] = AgentState.RUNNING
        payload = {**ctx, **node.input_payload}

        try:
            # Slight realistic async latency so concurrent multi-agent transitions can be observed
            await asyncio.sleep(0.3)

            if node.agent_id == "REVENUE":
                if "parse" in node.name.lower() or "rfq" in node.name.lower():
                    inquiry_text = payload.get("inquiry_text", "")
                    if not inquiry_text and "customer_name" in payload:
                        inquiry_text = f"Inquiry from {payload.get('customer_name')}: requested delivery date 2026-12-15"
                    extraction = await baml_client.parse_rfq_document(inquiry_text or "RFQ inquiry")
                    res = {
                        "customer_name": payload.get("customer_name") or extraction.customer_name,
                        "customer_email": payload.get("customer_email") or extraction.customer_email,
                        "requested_sku": extraction.line_items[0].requested_sku if extraction.line_items else "FG-ENCLOSURE-IP67",
                        "quantity": float(extraction.line_items[0].quantity) if extraction.line_items else 100.0,
                        "target_unit_price": float(extraction.line_items[0].target_unit_price) if extraction.line_items else 45.0,
                    }
                elif "quote" in node.name.lower():
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    material_cost = Decimal(str(payload.get("material_cost", "24.50")))
                    pricing = pricing_engine.calculate_margin_defended_price(sku=sku, bom_material_cost=material_cost)
                    res = {
                        "proposed_unit_price": float(pricing.proposed_unit_price),
                        "computed_margin_percentage": float(pricing.computed_margin_percentage),
                        "is_margin_compliant": pricing.is_margin_defended,
                    }
                else:
                    res = {"status": "SUCCESS", "node": node.name}

            elif node.agent_id == "SUPPLY_CHAIN":
                res = {
                    "material_cost": 24.50,
                    "lead_time_days": 7,
                    "supplier_name": "Verified Supply Partner",
                }

            elif node.agent_id == "PRODUCTION":
                qty = Decimal(str(payload.get("quantity", 100)))
                sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                job = JobSpec(
                    job_id=f"JOB-{node.task_id[:6]}",
                    job_name=f"Produce {qty} {sku}",
                    operations=[
                        JobOperationSpec(
                            operation_id="OP-01",
                            operation_name="Primary Machining",
                            workstation_code="WS-CNC-01",
                            duration_minutes=max(15, int(qty * Decimal("0.2"))),
                        )
                    ],
                )
                sched = cpsat_scheduler.solve_schedule(jobs=[job])
                res = {
                    "makespan_minutes": sched.makespan_minutes,
                    "assigned_workstations": ["WS-CNC-01"],
                }

            else:
                res = {"status": "SUCCESS", "node": node.name}

            node.output_result = res
            return res
        finally:
            chief_orchestrator.agent_states[node.agent_id] = AgentState.IDLE


dag_executor = DAGExecutor()
