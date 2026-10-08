import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import logging
import re
from typing import Any
import uuid

from sqlalchemy import select

from erp.baml_client.client import baml_client
from erp.commercial.pdf_generator import InvoiceData, InvoiceLineItem, invoice_pdf_generator
from erp.commercial.pricing_engine import pricing_engine
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel, Warehouse
from erp.db.models.sales import (
    Customer,
    DeliveryNote,
    DeliveryNoteItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
)
from erp.db.models.ledger import GeneralLedgerEntry
from erp.db.models.tenant import Tenant
from erp.db.session import async_session_factory
from erp.ledger.engine import TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
from erp.ledger.sales_posting import SalesPostingConfigurationError, resolve_sales_posting_configuration
from erp.orchestration.dag import TaskDAG, TaskNode, TaskStatus
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.guardrails import compliance_guardrail
from erp.orchestration.persistence import persist_dag_snapshot
from erp.orchestration.state import AgentActionProposal, AgentState
from erp.production.cpsat_scheduler import JobOperationSpec, JobSpec, cpsat_scheduler

logger = logging.getLogger(__name__)

NODE_GUARDRAIL_ACTIONS = {
    ("REVENUE", "parse rfq document"): "parse_rfq",
    ("SUPPLY_CHAIN", "calculate landed material costs"): "calculate_landed_costs",
    ("REVENUE", "generate margin-defended quote"): "generate_quotation",
    ("REVENUE", "extract order & buyer entity"): "parse_rfq",
    ("SUPPLY_CHAIN", "check inventory & stock availability"): "query_stock_atp",
    ("FINANCIAL_CONTROLLER", "fulfill delivery & post invoice to ledger"): "stage_ledger_transaction",
}


class DAGExecutor:
    """Executes hierarchical task DAGs across autonomous domain subagents."""

    async def execute_dag(self, dag: TaskDAG) -> dict[str, Any]:
        """Runs all DAG nodes to completion based on topological readiness."""
        logger.info("Starting execution of DAG %s (%d nodes)", dag.dag_id, len(dag.nodes))

        context_accumulator: dict[str, Any] = {}
        for node in dag.nodes.values():
            if node.status == TaskStatus.COMPLETED and isinstance(node.output_result, dict):
                context_accumulator[node.task_id] = node.output_result
                context_accumulator.update(node.output_result)
        await persist_dag_snapshot(dag)

        while not dag.is_finished():
            ready_nodes = dag.get_ready_tasks()
            if not ready_nodes:
                # If there are no ready nodes but DAG is not finished, check if there's deadlock or failure
                pending = [n for n in dag.nodes.values() if n.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
                if not pending:
                    await persist_dag_snapshot(dag)
                    break
                await asyncio.sleep(0.05)
                continue

            for node in ready_nodes:
                node.status = TaskStatus.RUNNING
                node.started_at = datetime.now(UTC)
            # Persist the claim before any node can perform a database or external side effect.
            await persist_dag_snapshot(dag)

            tasks = [
                self._execute_node(node, context_accumulator, dag.tenant_id)
                for node in ready_nodes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, res in zip(ready_nodes, results, strict=False):
                if isinstance(res, Exception):
                    logger.error("Node %s failed: %s", node.name, res)
                    dag.mark_failed(node.task_id, str(res))
                else:
                    result = res or {}
                    if isinstance(result, dict) and node.guardrail_evidence:
                        result["compliance_verification"] = node.guardrail_evidence
                    dag.mark_completed(node.task_id, result)
                    context_accumulator[node.task_id] = result
                    if isinstance(result, dict):
                        context_accumulator.update(result)
            await persist_dag_snapshot(dag)

        logger.info("DAG %s execution completed.", dag.dag_id)
        await persist_dag_snapshot(dag)
        return context_accumulator

    async def _execute_node(
        self, node: TaskNode, ctx: dict[str, Any], tenant_id_str: str | None
    ) -> dict[str, Any]:
        """Dispatches subtask execution according to agent_id and task name."""
        node.status = TaskStatus.RUNNING
        node.started_at = datetime.now(UTC)
        chief_orchestrator.agent_states[node.agent_id] = AgentState.RUNNING
        payload = {**ctx, **node.input_payload}
        if tenant_id_str:
            payload["tenant_id"] = tenant_id_str

        try:
            action_name = NODE_GUARDRAIL_ACTIONS.get((node.agent_id, node.name.lower()))
            if not action_name:
                raise PermissionError(
                    f"No compliance action policy is registered for {node.agent_id}:{node.name}."
                )
            tenant_id = uuid.UUID(payload["tenant_id"])
            proposal = AgentActionProposal(
                task_id=node.task_id,
                agent_id=node.agent_id,
                tenant_id=tenant_id,
                policy_class=(
                    "FINANCIAL_SOLVENCY"
                    if action_name == "stage_ledger_transaction"
                    else "CAPACITY_THROUGHPUT"
                ),
                resource_keys=[f"tenant:{tenant_id}", f"task:{node.task_id}"],
                state_mutation={"node_name": node.name, "task_id": node.task_id},
                audit_rationale=f"Guardrail check before executing DAG node '{node.name}'.",
            )
            evaluation = compliance_guardrail.evaluate_action_proposal(proposal, action_name)
            if not evaluation.is_compliant:
                raise PermissionError("Compliance guardrail rejected action: " + "; ".join(evaluation.violations))
            node.guardrail_evidence = {
                "action_name": evaluation.action_name,
                "verification_token": evaluation.verification_token,
                "evaluated_statutes": evaluation.evaluated_statutes,
            }

            if node.agent_id == "REVENUE":
                # 1. Order Extraction
                if "order" in node.name.lower() and ("extract" in node.name.lower() or "buyer" in node.name.lower()):
                    tenant_id_str = payload.get("tenant_id")
                    if not tenant_id_str:
                        raise ValueError("Order extraction requires an authoritative tenant_id.")
                    tenant_uuid = uuid.UUID(tenant_id_str)
                    inquiry_text = payload.get("inquiry_text", "")
                    sender = payload.get("customer_email") or payload.get("sender")
                    if not inquiry_text.strip() or not sender:
                        raise ValueError("Order extraction requires the original message and sender identity.")
                    subject = payload.get("subject") or "Inbound Order"

                    if inquiry_text.startswith("Subject:"):
                        parts = inquiry_text.split("\n\n", 1)
                        subj_line = parts[0].replace("Subject:", "").strip()
                        body_line = parts[1] if len(parts) > 1 else inquiry_text
                        if not payload.get("subject"):
                            subject = subj_line
                    else:
                        body_line = inquiry_text

                    from erp.commercial.gemini_order_agent import gemini_order_analyzer
                    analysis = await gemini_order_analyzer.analyze_inbound_email(
                        tenant_id=tenant_uuid,
                        sender=sender,
                        subject=subject,
                        body_text=body_line,
                    )

                    if not analysis.items:
                        raise ValueError("No order line items were identified; the message requires human review.")
                    if not analysis.customer_email and not payload.get("customer_email"):
                        raise ValueError("No verified customer email was identified; the message requires review.")

                    # Extract all items for multi-line support
                    extracted_items = []
                    for it_line in analysis.items:
                        it_code = it_line.matched_item_code or it_line.raw_item_query
                        it_name = it_line.matched_item_name or it_code
                        extracted_items.append({
                            "sku": it_code,
                            "raw_sku": it_line.raw_item_query,
                            "item_name": it_name,
                            "item_id": it_line.item_id,
                            "quantity": float(it_line.requested_qty),
                            "unit_price": float(it_line.unit_price),
                            "line_total": float(it_line.line_total),
                            "catalog_status": it_line.catalog_status,
                            "item_found_in_catalog": it_line.catalog_status in ("EXACT_MATCH", "FUZZY_MATCH"),
                            "is_in_stock": it_line.is_in_stock,
                            "available_qty": float(it_line.available_stock),
                        })

                    line = analysis.items[0] if analysis.items else None
                    sku = line.matched_item_code or line.raw_item_query
                    raw_sku = line.raw_item_query
                    qty = line.requested_qty
                    price = line.unit_price
                    if qty <= 0 or price <= 0:
                        raise ValueError("Order lines require positive quantities and explicit prices; human review is required.")
                    item_id_val = line.item_id
                    item_found = line.catalog_status in ("EXACT_MATCH", "FUZZY_MATCH")
                    item_name = line.matched_item_name or sku

                    if not extracted_items and line:
                        extracted_items.append({
                            "sku": sku,
                            "raw_sku": raw_sku,
                            "item_name": item_name,
                            "item_id": item_id_val,
                            "quantity": qty,
                            "unit_price": price,
                            "line_total": qty * price,
                            "catalog_status": line.catalog_status if line else "NOT_IN_CATALOG",
                            "item_found_in_catalog": item_found,
                            "is_in_stock": line.is_in_stock if line else False,
                            "available_qty": float(line.available_stock) if line else 0.0,
                        })

                    po_match = re.search(r"\b(PO[-_\s]?[A-Za-z0-9-]+)\b", inquiry_text, re.IGNORECASE)
                    po_num = po_match.group(1).upper().replace(" ", "-") if po_match else analysis.po_reference

                    # Ensure customer_email is a clean address
                    raw_email = analysis.customer_email or payload.get("customer_email") or payload.get("sender")
                    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_email)
                    if not email_match:
                        raise ValueError("Order sender does not contain a valid email address.")
                    clean_email = email_match.group(0)

                    order_total_val = sum(it["line_total"] for it in extracted_items) if extracted_items else (qty * price)
                    all_found = all(it["item_found_in_catalog"] for it in extracted_items) if extracted_items else item_found

                    res = {
                        "customer_name": payload.get("customer_name") or analysis.customer_name,
                        "customer_email": clean_email,
                        "po_number": po_num,
                        "requested_sku": sku,
                        "raw_item_query": raw_sku,
                        "item_name": item_name,
                        "quantity": qty,
                        "target_unit_price": price,
                        "order_total": float(order_total_val),
                        "items": extracted_items,
                        "intent": "CUSTOMER_ORDER" if (analysis.is_order or analysis.intent in ("ORDER", "CUSTOMER_ORDER")) else analysis.intent,
                        "is_order": analysis.is_order,
                        "item_id": item_id_val,
                        "item_found_in_catalog": all_found,
                        "catalog_match_status": line.catalog_status if line else "NOT_IN_CATALOG",
                        "analyzer_can_fulfill": analysis.can_fulfill,
                        "fulfillment_action": analysis.fulfillment_action,
                        "explanation": analysis.explanation,
                        "draft_email_response": analysis.draft_email_response,
                        "recommended_alternatives": analysis.recommended_alternatives,
                    }

                # 2. Inbound RFQ Parsing
                elif "parse" in node.name.lower() or "rfq" in node.name.lower():
                    inquiry_text = payload.get("inquiry_text", "")
                    if not inquiry_text.strip():
                        raise ValueError("RFQ text is required; no synthetic inquiry will be generated.")
                    extraction = await baml_client.parse_rfq_document(inquiry_text)
                    res = {
                        "customer_name": payload.get("customer_name") or extraction.customer_name,
                        "customer_email": payload.get("customer_email") or extraction.customer_email,
                        "requested_sku": extraction.line_items[0].requested_sku if extraction.line_items else None,
                        "quantity": float(extraction.line_items[0].quantity) if extraction.line_items else None,
                        "target_unit_price": float(extraction.line_items[0].target_unit_price) if extraction.line_items else None,
                        "intent": "CUSTOMER_RFQ",
                    }

                # 3. Dynamic Quote Generation
                elif "quote" in node.name.lower():
                    sku = payload.get("requested_sku")
                    material_cost_value = payload.get("material_cost")
                    if not sku or material_cost_value is None:
                        raise ValueError("Quote requires a parsed SKU and verified tenant BOM material cost.")
                    material_cost = Decimal(str(material_cost_value))
                    pricing = pricing_engine.calculate_margin_defended_price(sku=sku, bom_material_cost=material_cost)
                    res = {
                        "proposed_unit_price": float(pricing.proposed_unit_price),
                        "computed_margin_percentage": float(pricing.computed_margin_percentage),
                        "is_margin_compliant": pricing.is_margin_defended,
                    }

                # 4. Auto-Provision Customer & Confirmed Sales Order
                elif "provision" in node.name.lower() or "sales order" in node.name.lower():
                    tenant_id_str = payload.get("tenant_id")
                    tenant_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.UUID("00000000-0000-0000-0000-000000000001")
                    cust_name = payload.get("customer_name") or "Commercial Client"
                    cust_email = payload.get("customer_email") or f"orders@{cust_name.lower().replace(' ', '')}.com"
                    po_num = payload.get("po_number") or f"PO-{uuid.uuid4().hex[:6].upper()}"
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    raw_sku = payload.get("raw_item_query", sku)
                    qty = Decimal(str(payload.get("quantity", 10.0)))
                    item_found = payload.get("item_found_in_catalog", True)
                    is_in_stock = payload.get("is_in_stock", True)

                    if not item_found:
                        res = {
                            "customer_id": None,
                            "customer_name": cust_name,
                            "customer_code": None,
                            "order_id": None,
                            "order_number": None,
                            "order_total": 0.0,
                            "stock_reserved": 0.0,
                            "item_id": None,
                            "warehouse_id": None,
                            "status": "REJECTED_CATALOG_MISMATCH",
                            "fulfillment_status": "ITEM_NOT_FOUND_IN_CATALOG",
                        }
                    else:
                        async with async_session_factory() as s:
                            # Find or create customer
                            stmt = select(Customer).where(Customer.tenant_id == tenant_uuid)
                            if cust_email:
                                stmt = stmt.where(Customer.email == cust_email)
                            else:
                                stmt = stmt.where(Customer.customer_name == cust_name)
                            cust = (await s.execute(stmt)).scalars().first()
                            if not cust:
                                cust = Customer(
                                    tenant_id=tenant_uuid,
                                    customer_code=f"CUST-{uuid.uuid4().hex[:6].upper()}",
                                    customer_name=cust_name,
                                    email=cust_email,
                                    credit_limit=Decimal("100000.0000"),
                                )
                                s.add(cust)
                                await s.flush()

                            # Lookup items from DB to ensure real catalog rates and IDs are used
                            raw_items = payload.get("items") or []
                            order_items_to_create = []
                            total_amt = Decimal("0.0000")

                            if raw_items:
                                for it_dict in raw_items:
                                    it_sku = it_dict.get("sku") or it_dict.get("requested_sku")
                                    it_qty = Decimal(str(it_dict.get("quantity", 1.0)))
                                    it_id_str = it_dict.get("item_id")
                                    it_uuid = uuid.UUID(it_id_str) if it_id_str else None

                                    item_stmt = select(Item).where(Item.tenant_id == tenant_uuid)
                                    if it_uuid:
                                        item_stmt = item_stmt.where(Item.item_id == it_uuid)
                                    else:
                                        item_stmt = item_stmt.where(Item.item_code == it_sku)
                                    db_item = (await s.execute(item_stmt)).scalar_one_or_none()

                                    if db_item:
                                        it_price = db_item.standard_rate
                                        it_id = db_item.item_id
                                    else:
                                        it_price = Decimal(str(it_dict.get("unit_price", 10.0)))
                                        it_id = it_uuid or uuid.uuid4()

                                    line_amt = (it_qty * it_price).quantize(Decimal("0.0001"))
                                    total_amt += line_amt
                                    order_items_to_create.append({
                                        "item_id": it_id,
                                        "sku": it_sku,
                                        "quantity": it_qty,
                                        "unit_price": it_price,
                                        "line_total": line_amt,
                                        "warehouse_id": it_dict.get("warehouse_id"),
                                        "is_in_stock": it_dict.get("is_in_stock", is_in_stock),
                                    })
                            else:
                                item_stmt = select(Item).where(Item.tenant_id == tenant_uuid, Item.item_code == sku)
                                item = (await s.execute(item_stmt)).scalar_one_or_none()
                                if item:
                                    unit_price = item.standard_rate
                                    item_id = item.item_id
                                else:
                                    unit_price = Decimal(str(payload.get("target_unit_price", 10.0)))
                                    item_id = uuid.UUID(payload["item_id"]) if payload.get("item_id") else uuid.uuid4()
                                total_amt = (qty * unit_price).quantize(Decimal("0.0001"))
                                order_items_to_create.append({
                                    "item_id": item_id,
                                    "sku": sku,
                                    "quantity": qty,
                                    "unit_price": unit_price,
                                    "line_total": total_amt,
                                    "warehouse_id": payload.get("warehouse_id"),
                                    "is_in_stock": is_in_stock,
                                })

                            so_status = "CONFIRMED" if is_in_stock else "BACKORDERED"

                            so_num = f"SO-{po_num.replace('PO-', '')}"
                            order = SalesOrder(
                                tenant_id=tenant_uuid,
                                order_number=so_num,
                                customer_id=cust.customer_id,
                                order_date=date.today(),
                                delivery_date=date.today(),
                                total_amount=total_amt,
                                status=so_status,
                            )
                            s.add(order)
                            await s.flush()

                            total_stock_reserved = Decimal("0.0000")
                            created_item_results = []
                            for oi in order_items_to_create:
                                so_item = SalesOrderItem(
                                    tenant_id=tenant_uuid,
                                    order_id=order.order_id,
                                    item_id=oi["item_id"],
                                    quantity=oi["quantity"],
                                    unit_price=oi["unit_price"],
                                    line_total=oi["line_total"],
                                )
                                s.add(so_item)

                                # Reserve stock in inventory if available
                                oi_wh_id_str = oi["warehouse_id"]
                                oi_wh_id = uuid.UUID(oi_wh_id_str) if oi_wh_id_str else None
                                it_reserved = Decimal("0.0000")

                                if is_in_stock and oi["is_in_stock"]:
                                    stk_stmt = (
                                        select(StockLevel, Warehouse)
                                        .join(Warehouse, Warehouse.warehouse_id == StockLevel.warehouse_id)
                                        .where(
                                            StockLevel.tenant_id == tenant_uuid,
                                            StockLevel.item_id == oi["item_id"],
                                            Warehouse.is_active.is_(True),
                                        )
                                    )
                                    if oi_wh_id:
                                        stk_stmt = stk_stmt.where(StockLevel.warehouse_id == oi_wh_id)
                                    stk_rows = (await s.execute(stk_stmt)).all()
                                    if stk_rows:
                                        stk_row = next((r for r in stk_rows if r[0].available_qty >= oi["quantity"]), stk_rows[0])
                                        stk, wh_obj = stk_row[0], stk_row[1]
                                        oi_wh_id = wh_obj.warehouse_id
                                        stk.reserved_qty += oi["quantity"]
                                        stk.available_qty = stk.current_qty - stk.reserved_qty
                                        it_reserved = oi["quantity"]
                                        total_stock_reserved += it_reserved

                                created_item_results.append({
                                    "item_id": str(oi["item_id"]),
                                    "sku": oi["sku"],
                                    "quantity": float(oi["quantity"]),
                                    "unit_price": float(oi["unit_price"]),
                                    "line_total": float(oi["line_total"]),
                                    "warehouse_id": str(oi_wh_id) if oi_wh_id else None,
                                    "is_in_stock": oi["is_in_stock"],
                                    "stock_reserved": float(it_reserved),
                                })

                            await s.commit()

                            first_res = created_item_results[0] if created_item_results else {}
                            res = {
                                "customer_id": str(cust.customer_id),
                                "customer_name": cust.customer_name,
                                "customer_code": cust.customer_code,
                                "order_id": str(order.order_id),
                                "order_number": order.order_number,
                                "order_total": float(total_amt),
                                "target_unit_price": first_res.get("unit_price", float(payload.get("target_unit_price", 10.0))),
                                "stock_reserved": float(total_stock_reserved),
                                "item_id": first_res.get("item_id"),
                                "warehouse_id": first_res.get("warehouse_id"),
                                "items": created_item_results,
                                "status": so_status,
                            }

                # 5. Outbound Order Confirmation & Invoice Dispatch
                elif "dispatch" in node.name.lower():
                    tenant_id_str = payload.get("tenant_id") or "00000000-0000-0000-0000-000000000001"
                    cust_email = payload.get("customer_email") or "orders@customer.internal"
                    cust_name = payload.get("customer_name") or "Valued Customer"
                    order_num = payload.get("order_number") or "SO-PENDING"
                    is_in_stock = payload.get("is_in_stock", True)
                    item_found = payload.get("item_found_in_catalog", True)
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    raw_sku = payload.get("raw_item_query", sku)
                    item_desc = payload.get("item_name") or f"Standard {sku}"
                    req_qty = float(payload.get("requested_qty") or payload.get("quantity") or 10.0)
                    avail_qty = float(payload.get("available_qty", 0.0))
                    draft_resp = payload.get("draft_email_response")
                    alts = payload.get("recommended_alternatives", [])

                    if not item_found:
                        # 1. Item NOT in Catalog: Notify customer & offer catalog alternatives
                        subject = f"Regarding your order request for {raw_sku} - Product Availability Update"
                        body = draft_resp or (
                            f"Dear {cust_name},\n\n"
                            f"Thank you for contacting us. We received your order request for {req_qty:,.0f} units of '{raw_sku}'.\n\n"
                            f"However, '{raw_sku}' is not currently available in our product catalog.\n\n"
                            f"Please let us know if you would like to place an order for one of our active products instead.\n\n"
                            f"Autonomous Sales & Customer Success\n"
                            f"AI-Native Enterprise Resource Planning"
                        )
                        sent_via = "OUTBOUND_MAILER"
                        try:
                            from erp.events.gmail_integration import gmail_service
                            conn = await gmail_service.ensure_valid_token(tenant_id_str)
                            if conn.is_connected:
                                await gmail_service.send_email_via_gmail(
                                    tenant_id=tenant_id_str,
                                    recipient=cust_email,
                                    subject=subject,
                                    body=body,
                                )
                                sent_via = "GMAIL_OAUTH_API"
                            else:
                                from erp.events.email_gateway import outbound_mailer
                                await outbound_mailer.dispatch_catalog_mismatch_email(
                                    recipient_email=cust_email,
                                    customer_name=cust_name,
                                    requested_sku=raw_sku,
                                    requested_qty=req_qty,
                                    recommended_alternatives=alts,
                                    custom_body=body,
                                    tenant_id=tenant_id_str,
                                )
                        except Exception as e:
                            logger.warning("Could not send via Gmail (%s), falling back to outbound mailer", e)
                            from erp.events.email_gateway import outbound_mailer
                            await outbound_mailer.dispatch_catalog_mismatch_email(
                                recipient_email=cust_email,
                                customer_name=cust_name,
                                requested_sku=raw_sku,
                                requested_qty=req_qty,
                                recommended_alternatives=alts,
                                custom_body=body,
                                tenant_id=tenant_id_str,
                            )

                        res = {
                            "confirmation_dispatched": True,
                            "email_type": "CATALOG_MISMATCH_RECOMMENDATION",
                            "recipient": cust_email,
                            "order_number": order_num,
                            "stock_status": "ITEM_NOT_IN_CATALOG",
                            "sent_via": sent_via,
                            "sla": "Notification delivered within 300 seconds",
                        }

                    elif not is_in_stock:
                        # 2. Stock Shortage: Reply with Backorder & ETA Notice
                        subject = f"Order Notification: Inventory Backorder Update for Order {order_num}"
                        body = draft_resp or (
                            f"Dear {cust_name},\n\n"
                            f"Thank you for your order {order_num} for {req_qty:,.0f} units of {sku}.\n\n"
                            f"Our autonomous inventory engine has verified current stock availability. "
                            f"We currently have {avail_qty:,.0f} units on hand, which is insufficient to immediately fulfill your full request.\n\n"
                            f"We have automatically placed your order on prioritized BACKORDER and triggered an immediate "
                            f"manufacturing replenishment work order. The estimated delivery lead time is 7 business days.\n\n"
                            f"We apologize for the brief delay and will send you a dispatch notification and invoice as soon as the batch is completed.\n\n"
                            f"Autonomous Supply Chain Operations\n"
                            f"AI-Native Enterprise Resource Planning"
                        )
                        sent_via = "OUTBOUND_MAILER"
                        try:
                            from erp.events.gmail_integration import gmail_service
                            conn = await gmail_service.ensure_valid_token(tenant_id_str)
                            if conn.is_connected:
                                await gmail_service.send_email_via_gmail(
                                    tenant_id=tenant_id_str,
                                    recipient=cust_email,
                                    subject=subject,
                                    body=body,
                                )
                                sent_via = "GMAIL_OAUTH_API"
                            else:
                                from erp.events.email_gateway import outbound_mailer
                                await outbound_mailer.dispatch_shortage_notice_email(
                                    recipient_email=cust_email,
                                    customer_name=cust_name,
                                    order_number=order_num,
                                    requested_sku=sku,
                                    requested_qty=req_qty,
                                    available_qty=avail_qty,
                                    tenant_id=tenant_id_str,
                                )
                        except Exception as e:
                            logger.warning("Could not send via Gmail (%s), falling back to outbound mailer", e)
                            from erp.events.email_gateway import outbound_mailer
                            await outbound_mailer.dispatch_shortage_notice_email(
                                recipient_email=cust_email,
                                customer_name=cust_name,
                                order_number=order_num,
                                requested_sku=sku,
                                requested_qty=req_qty,
                                available_qty=avail_qty,
                                tenant_id=tenant_id_str,
                            )

                        res = {
                            "confirmation_dispatched": True,
                            "email_type": "INVENTORY_SHORTAGE_NOTIFICATION",
                            "recipient": cust_email,
                            "order_number": order_num,
                            "stock_status": "SHORTAGE_BACKORDERED",
                            "sent_via": sent_via,
                            "lead_time_days": 7,
                            "sla": "Notification delivered within 300 seconds",
                        }

                    else:
                        # 3. Stock Available: Generate PDF Sales Invoice & Deliver to Customer
                        inv_num = payload.get("invoice_number", f"INV-{order_num.replace('SO-', '')}")
                        dn_num = payload.get("delivery_note_number", f"DN-{order_num}")
                        inv_amt = float(payload.get("invoice_amount") or payload.get("order_total") or 0.0)

                        raw_items = payload.get("items") or []
                        inv_line_items = []
                        if raw_items:
                            for it in raw_items:
                                it_sku = it.get("sku") or it.get("requested_sku") or sku
                                it_desc = it.get("item_name") or f"Standard {it_sku}"
                                it_qty = Decimal(str(it.get("quantity", 1.0)))
                                it_price = Decimal(str(it.get("unit_price") or it.get("target_unit_price", 0.0))).quantize(Decimal("0.01"))
                                it_total = Decimal(str(it.get("line_total") or (float(it_qty) * float(it_price)))).quantize(Decimal("0.01"))
                                inv_line_items.append(
                                    InvoiceLineItem(
                                        item_code=it_sku,
                                        description=it_desc,
                                        quantity=it_qty,
                                        unit_price=it_price,
                                        line_total=it_total,
                                    )
                                )
                        else:
                            unit_rate = (inv_amt / max(req_qty, 1.0))
                            inv_line_items.append(
                                InvoiceLineItem(
                                    item_code=sku,
                                    description=item_desc,
                                    quantity=Decimal(str(req_qty)),
                                    unit_price=Decimal(str(unit_rate)).quantize(Decimal("0.01")),
                                    line_total=Decimal(str(inv_amt)).quantize(Decimal("0.01")),
                                )
                            )

                        subtotal_amt = sum((it.line_total for it in inv_line_items), Decimal("0.00"))
                        if subtotal_amt == Decimal("0.00") and inv_amt > 0:
                            subtotal_amt = Decimal(str(inv_amt)).quantize(Decimal("0.01"))

                        # Generate official PDF invoice bytes with real catalog items
                        inv_data = InvoiceData(
                            invoice_number=inv_num,
                            order_number=order_num,
                            delivery_note_number=dn_num,
                            customer_name=cust_name,
                            customer_email=cust_email,
                            items=inv_line_items,
                            subtotal=subtotal_amt,
                            tax_amount=Decimal("0.00"),
                            total_amount=subtotal_amt,
                        )
                        pdf_bytes = invoice_pdf_generator.generate_pdf(inv_data)

                        items_summary = "\n".join([
                            f"  • {item.description} ({item.item_code}): {item.quantity:,.0f} units @ ${item.unit_price:,.2f} = ${item.line_total:,.2f}"
                            for item in inv_line_items
                        ])

                        subject = f"Order Confirmation & Sales Invoice {inv_num} for Order {order_num}"
                        body = (
                            f"Dear {cust_name},\n\n"
                            f"Thank you for your order {order_num}! Your purchase has been confirmed and fulfilled.\n\n"
                            f"Order Reference: {order_num}\n"
                            f"Delivery Note: {dn_num}\n"
                            f"Sales Invoice: {inv_num}\n\n"
                            f"Order Items:\n{items_summary}\n\n"
                            f"Total Amount: ${float(subtotal_amt):,.2f} USD\n\n"
                            f"Your order has been allocated and delivered from our warehouse. "
                            f"Please find attached your official Sales Invoice PDF.\n\n"
                            f"Autonomous Revenue & Fulfillment Agent\n"
                            f"AI-Native Enterprise Resource Planning"
                        )
                        sent_via = "OUTBOUND_MAILER"
                        try:
                            from erp.events.gmail_integration import gmail_service
                            conn = await gmail_service.ensure_valid_token(tenant_id_str)
                            if conn.is_connected:
                                await gmail_service.send_email_via_gmail(
                                    tenant_id=tenant_id_str,
                                    recipient=cust_email,
                                    subject=subject,
                                    body=body,
                                    pdf_bytes=pdf_bytes,
                                    filename=f"{inv_num}.pdf",
                                )
                                sent_via = "GMAIL_OAUTH_API"
                            else:
                                from erp.events.email_gateway import outbound_mailer
                                await outbound_mailer.dispatch_invoice_email(
                                    recipient_email=cust_email,
                                    customer_name=cust_name,
                                    order_number=order_num,
                                    invoice_number=inv_num,
                                    total_amount=inv_amt,
                                    pdf_bytes=pdf_bytes,
                                    tenant_id=tenant_id_str,
                                )
                        except Exception as e:
                            logger.warning("Could not send via Gmail (%s), falling back to outbound mailer", e)
                            from erp.events.email_gateway import outbound_mailer
                            await outbound_mailer.dispatch_invoice_email(
                                recipient_email=cust_email,
                                customer_name=cust_name,
                                order_number=order_num,
                                invoice_number=inv_num,
                                total_amount=inv_amt,
                                pdf_bytes=pdf_bytes,
                                tenant_id=tenant_id_str,
                            )

                        res = {
                            "confirmation_dispatched": True,
                            "email_type": "SALES_INVOICE_DISPATCH",
                            "recipient": cust_email,
                            "order_number": order_num,
                            "invoice_delivered": inv_num,
                            "invoice_amount": inv_amt,
                            "stock_status": "AVAILABLE_FULFILLED",
                            "sent_via": sent_via,
                            "pdf_attached": f"{inv_num}.pdf",
                            "sla": "Dispatched within 300 seconds",
                        }
                else:
                    res = {"status": "SUCCESS", "node": node.name}

            elif node.agent_id == "SUPPLY_CHAIN":
                # Real Warehouse Stock Availability Check
                if "stock" in node.name.lower() or "inventory" in node.name.lower() or "availability" in node.name.lower():
                    tenant_id_str = payload.get("tenant_id")
                    if not tenant_id_str:
                        raise ValueError("Inventory lookup requires an authoritative tenant_id.")
                    tenant_uuid = uuid.UUID(tenant_id_str)
                    sku = payload.get("requested_sku")
                    if not sku:
                        raise ValueError("Inventory lookup requires an explicitly parsed SKU.")
                    raw_sku = payload.get("raw_item_query", sku)
                    quantity_value = payload.get("quantity")
                    if quantity_value is None or Decimal(str(quantity_value)) <= 0:
                        raise ValueError("Inventory lookup requires an explicit positive quantity.")
                    qty = Decimal(str(quantity_value))
                    item_found = payload.get("item_found_in_catalog", True)

                    raw_items = payload.get("items") or []

                    async with async_session_factory() as s:
                        wh_stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_uuid, Warehouse.is_active.is_(True))
                        all_whs = (await s.execute(wh_stmt)).scalars().all()
                        default_wh = all_whs[0] if all_whs else None
                        if not default_wh:
                            raise ValueError("Tenant has no active warehouse; inventory availability is unknown.")

                        if raw_items:
                            checked_items = []
                            all_in_stock = True
                            all_found = True
                            for it_dict in raw_items:
                                it_sku = it_dict.get("sku") or it_dict.get("requested_sku")
                                it_id_s = it_dict.get("item_id")
                                it_uuid = uuid.UUID(it_id_s) if it_id_s else None
                                it_qty = Decimal(str(it_dict.get("quantity", 1.0)))

                                item_stmt = select(Item).where(Item.tenant_id == tenant_uuid)
                                if it_uuid:
                                    item_stmt = item_stmt.where(Item.item_id == it_uuid)
                                else:
                                    item_stmt = item_stmt.where(Item.item_code == it_sku)
                                item = (await s.execute(item_stmt)).scalar_one_or_none()

                                if not item:
                                    all_found = False
                                    all_in_stock = False
                                    checked_items.append({
                                        **it_dict,
                                        "item_found_in_catalog": False,
                                        "is_in_stock": False,
                                        "available_qty": 0.0,
                                        "current_on_hand_qty": 0.0,
                                        "reserved_qty": 0.0,
                                        "warehouse_id": str(default_wh.warehouse_id),
                                        "warehouse_code": default_wh.warehouse_code,
                                    })
                                else:
                                    stk_stmt = (
                                        select(StockLevel, Warehouse)
                                        .join(Warehouse, Warehouse.warehouse_id == StockLevel.warehouse_id)
                                        .where(
                                            StockLevel.tenant_id == tenant_uuid,
                                            StockLevel.item_id == item.item_id,
                                            Warehouse.is_active.is_(True),
                                        )
                                    )
                                    stk_rows = (await s.execute(stk_stmt)).all()
                                    wh_with_stock = next((r for r in stk_rows if r[0].available_qty >= it_qty), None)
                                    if not wh_with_stock and stk_rows:
                                        wh_with_stock = max(stk_rows, key=lambda r: r[0].available_qty)

                                    if wh_with_stock:
                                        stk, chosen_wh = wh_with_stock[0], wh_with_stock[1]
                                        curr_qty = stk.current_qty
                                        res_qty = stk.reserved_qty
                                        avail_qty = stk.available_qty
                                    else:
                                        chosen_wh = default_wh
                                        curr_qty = Decimal("0.0000")
                                        res_qty = Decimal("0.0000")
                                        avail_qty = Decimal("0.0000")

                                    it_in_stock = avail_qty >= it_qty
                                    if not it_in_stock:
                                        all_in_stock = False

                                    checked_items.append({
                                        **it_dict,
                                        "item_id": str(item.item_id),
                                        "sku": item.item_code,
                                        "item_name": item.item_name,
                                        "unit_price": float(item.standard_rate),
                                        "line_total": float(it_qty * item.standard_rate),
                                        "warehouse_id": str(chosen_wh.warehouse_id),
                                        "warehouse_code": chosen_wh.warehouse_code,
                                        "current_on_hand_qty": float(curr_qty),
                                        "reserved_qty": float(res_qty),
                                        "available_qty": float(avail_qty),
                                        "is_in_stock": bool(it_in_stock),
                                        "item_found_in_catalog": True,
                                    })

                            first_it = checked_items[0] if checked_items else {}
                            res = {
                                "is_in_stock": all_in_stock,
                                "item_found_in_catalog": all_found,
                                "items": checked_items,
                                "order_total": sum(i["line_total"] for i in checked_items),
                                "warehouse_code": first_it.get("warehouse_code", default_wh.warehouse_code),
                                "warehouse_id": first_it.get("warehouse_id", str(default_wh.warehouse_id)),
                                "item_id": first_it.get("item_id"),
                                "requested_sku": first_it.get("sku"),
                                "item_name": first_it.get("item_name"),
                                "target_unit_price": first_it.get("unit_price", 0.0),
                                "requested_qty": first_it.get("quantity", 0.0),
                                "current_on_hand_qty": first_it.get("current_on_hand_qty", 0.0),
                                "reserved_qty": first_it.get("reserved_qty", 0.0),
                                "available_qty": first_it.get("available_qty", 0.0),
                                "fulfillment_status": "STOCK_AVAILABLE_READY_TO_FULFILL" if all_in_stock else ("ITEM_NOT_FOUND_IN_CATALOG" if not all_found else "SHORTAGE_BACKORDER_TRIGGERED"),
                            }
                        else:
                            item_stmt = select(Item).where(Item.tenant_id == tenant_uuid, Item.item_code == sku)
                            item = (await s.execute(item_stmt)).scalar_one_or_none()

                            if not item:
                                res = {
                                    "is_in_stock": False,
                                    "item_found_in_catalog": False,
                                    "warehouse_code": default_wh.warehouse_code,
                                    "warehouse_id": str(default_wh.warehouse_id),
                                    "item_id": None,
                                    "requested_qty": float(qty),
                                    "current_on_hand_qty": 0.0,
                                    "reserved_qty": 0.0,
                                    "available_qty": 0.0,
                                    "fulfillment_status": "ITEM_NOT_FOUND_IN_CATALOG",
                                    "explanation": f"Item '{raw_sku}' does not exist in product catalog.",
                                }
                            else:
                                stk_stmt = (
                                    select(StockLevel, Warehouse)
                                    .join(Warehouse, Warehouse.warehouse_id == StockLevel.warehouse_id)
                                    .where(
                                        StockLevel.tenant_id == tenant_uuid,
                                        StockLevel.item_id == item.item_id,
                                        Warehouse.is_active.is_(True),
                                    )
                                )
                                stk_rows = (await s.execute(stk_stmt)).all()

                                # Pick warehouse with available stock >= qty, or warehouse with max available stock
                                wh_with_stock = next((r for r in stk_rows if r[0].available_qty >= qty), None)
                                if not wh_with_stock and stk_rows:
                                    wh_with_stock = max(stk_rows, key=lambda r: r[0].available_qty)

                                if wh_with_stock:
                                    stk, chosen_wh = wh_with_stock[0], wh_with_stock[1]
                                    curr_qty = stk.current_qty
                                    res_qty = stk.reserved_qty
                                    avail_qty = stk.available_qty
                                else:
                                    chosen_wh = default_wh
                                    curr_qty = Decimal("0.0000")
                                    res_qty = Decimal("0.0000")
                                    avail_qty = Decimal("0.0000")

                                is_in_stock = avail_qty >= qty
                                res = {
                                    "is_in_stock": bool(is_in_stock),
                                    "item_found_in_catalog": True,
                                    "warehouse_code": chosen_wh.warehouse_code,
                                    "warehouse_id": str(chosen_wh.warehouse_id),
                                    "item_id": str(item.item_id),
                                    "requested_sku": item.item_code,
                                    "item_name": item.item_name,
                                    "target_unit_price": float(item.standard_rate),
                                    "requested_qty": float(qty),
                                    "current_on_hand_qty": float(curr_qty),
                                    "reserved_qty": float(res_qty),
                                    "available_qty": float(avail_qty),
                                    "fulfillment_status": "STOCK_AVAILABLE_READY_TO_FULFILL" if is_in_stock else "SHORTAGE_BACKORDER_TRIGGERED",
                                }
                else:
                    # No supplier quote/BOM cost source is wired to this node yet.
                    res = {"status": "UNAVAILABLE", "reason": "No verified material cost source is configured."}

            elif node.agent_id == "FINANCIAL_CONTROLLER":
                if "fulfill" in node.name.lower() or "invoice" in node.name.lower() or "ledger" in node.name.lower():
                    is_in_stock = payload.get("is_in_stock", True)
                    item_found = payload.get("item_found_in_catalog", True)
                    order_num = payload.get("order_number")

                    if not is_in_stock or not item_found or not order_num:
                        res = {
                            "delivery_note_number": None,
                            "invoice_number": None,
                            "general_ledger_status": "HOLD_PENDING_STOCK_REPLENISHMENT" if item_found else "HOLD_CATALOG_MISMATCH",
                            "fulfillment_status": "SHORTAGE_BACKORDER_HELD" if item_found else "ITEM_NOT_IN_CATALOG_HELD",
                            "shortage_reason": payload.get("explanation") or f"Inventory or catalog unfulfillable for SKU {payload.get('requested_sku', 'item')}.",
                        }
                    else:
                        tenant_id_str = payload.get("tenant_id")
                        if not tenant_id_str:
                            raise ValueError("Fulfillment requires an authoritative tenant_id.")
                        tenant_uuid = uuid.UUID(tenant_id_str)
                        order_id_str = payload.get("order_id")
                        order_uuid = uuid.UUID(order_id_str) if order_id_str else None
                        order_num = payload.get("order_number")
                        cust_id_str = payload.get("customer_id")
                        cust_uuid = uuid.UUID(cust_id_str) if cust_id_str else None
                        wh_id_str = payload.get("warehouse_id")
                        wh_uuid = uuid.UUID(wh_id_str) if wh_id_str else None
                        item_id_str = payload.get("item_id")
                        item_uuid = uuid.UUID(item_id_str) if item_id_str else None
                        qty = Decimal(str(payload.get("quantity", 0)))
                        total_amt = Decimal(str(payload.get("order_total", 0)))

                        raw_items = payload.get("items") or []

                        async with async_session_factory() as s:
                            # Lock and validate the authoritative records before creating any
                            # fulfillment artifacts. Upstream availability is only advisory.
                            if not all((order_uuid, cust_uuid, order_num)) or not (raw_items or (item_uuid and wh_uuid)):
                                return {
                                    "delivery_note_number": None,
                                    "invoice_number": None,
                                    "general_ledger_status": "HOLD_MISSING_ORDER_DATA",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": "Order, customer, warehouse, and item data are required.",
                                }

                            order = (await s.execute(
                                select(SalesOrder).where(
                                    SalesOrder.tenant_id == tenant_uuid,
                                    SalesOrder.order_id == order_uuid,
                                    SalesOrder.order_number == order_num,
                                ).with_for_update()
                            )).scalar_one_or_none()
                            customer = (await s.execute(
                                select(Customer).where(
                                    Customer.tenant_id == tenant_uuid,
                                    Customer.customer_id == cust_uuid,
                                    Customer.is_active.is_(True),
                                )
                            )).scalar_one_or_none()
                            if not order or not customer or order.status not in {"CONFIRMED", "BACKORDERED"}:
                                return {
                                    "delivery_note_number": None,
                                    "invoice_number": None,
                                    "general_ledger_status": "HOLD_INVALID_ORDER_OR_CUSTOMER",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": "The order or customer is missing, inactive, tenant-mismatched, or not confirmed for fulfillment.",
                                }

                            existing_delivery = (await s.execute(
                                select(DeliveryNote).where(
                                    DeliveryNote.tenant_id == tenant_uuid,
                                    DeliveryNote.order_id == order_uuid,
                                ).with_for_update()
                            )).scalar_one_or_none()
                            if existing_delivery:
                                existing_invoice = (await s.execute(
                                    select(SalesInvoice).where(
                                        SalesInvoice.tenant_id == tenant_uuid,
                                        SalesInvoice.order_id == order_uuid,
                                        SalesInvoice.delivery_note_id == existing_delivery.delivery_note_id,
                                    )
                                )).scalar_one_or_none()
                                existing_entries = []
                                if existing_invoice:
                                    existing_entries = (await s.execute(
                                        select(GeneralLedgerEntry).where(
                                            GeneralLedgerEntry.tenant_id == tenant_uuid,
                                            GeneralLedgerEntry.source_document_type == "SALES_INVOICE",
                                            GeneralLedgerEntry.source_document_id == existing_invoice.invoice_id,
                                        )
                                    )).scalars().all()
                                debits = sum((entry.debit_amount for entry in existing_entries), Decimal("0.0000"))
                                credits = sum((entry.credit_amount for entry in existing_entries), Decimal("0.0000"))
                                if existing_invoice and len(existing_entries) >= 2 and debits == credits and debits > 0:
                                    return {
                                        "delivery_note_number": existing_delivery.delivery_note_number,
                                        "invoice_number": existing_invoice.invoice_number,
                                        "invoice_amount": float(existing_invoice.total_amount),
                                        "general_ledger_status": "ALREADY_COMMITTED_AR_AND_REVENUE",
                                        "fulfillment_status": "ALREADY_DELIVERED_AND_INVOICED",
                                        "gl_posted": True,
                                        "idempotent_replay": True,
                                    }
                                return {
                                    "delivery_note_number": existing_delivery.delivery_note_number,
                                    "invoice_number": existing_invoice.invoice_number if existing_invoice else None,
                                    "general_ledger_status": "HOLD_RECONCILIATION_REQUIRED",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": "Prior fulfillment records exist without a confirmed balanced invoice journal; reconcile before retry.",
                                }

                            tenant = (await s.execute(
                                select(Tenant).where(Tenant.tenant_id == tenant_uuid)
                            )).scalar_one_or_none()
                            if not tenant:
                                raise ValueError("Fulfillment tenant no longer exists.")
                            currency = tenant.currency
                            try:
                                ar_account, revenue_account, cost_center = await resolve_sales_posting_configuration(
                                    s, tenant_uuid, currency
                                )
                            except SalesPostingConfigurationError as exc:
                                return {
                                    "delivery_note_number": None,
                                    "invoice_number": None,
                                    "general_ledger_status": "HOLD_LEDGER_CONFIGURATION",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": str(exc),
                                }

                            lines_to_fulfill = raw_items or [{
                                "item_id": str(item_uuid), "warehouse_id": str(wh_uuid),
                                "quantity": str(qty), "unit_price": str(order.total_amount / qty if qty else 0),
                                "line_total": str(order.total_amount),
                            }]
                            order_lines = (await s.execute(
                                select(SalesOrderItem).where(
                                    SalesOrderItem.tenant_id == tenant_uuid,
                                    SalesOrderItem.order_id == order_uuid,
                                ).with_for_update()
                            )).scalars().all()
                            ordered_qty_by_item: dict[uuid.UUID, Decimal] = {}
                            order_price_by_item: dict[uuid.UUID, Decimal] = {}
                            for order_line in order_lines:
                                ordered_qty_by_item[order_line.item_id] = (
                                    ordered_qty_by_item.get(order_line.item_id, Decimal("0.0000"))
                                    + order_line.quantity
                                )
                                existing_price = order_price_by_item.get(order_line.item_id)
                                if existing_price is not None and existing_price != order_line.unit_price:
                                    return {
                                        "delivery_note_number": None,
                                        "invoice_number": None,
                                        "general_ledger_status": "HOLD_AMBIGUOUS_ORDER_PRICING",
                                        "fulfillment_status": "FULFILLMENT_HELD",
                                        "shortage_reason": "The sales order has multiple prices for the same item and needs manual review.",
                                    }
                                order_price_by_item[order_line.item_id] = order_line.unit_price
                            requested_qty_by_item: dict[uuid.UUID, Decimal] = {}
                            computed_total = Decimal("0.0000")
                            locked_stock: dict[tuple[uuid.UUID, uuid.UUID], StockLevel] = {}
                            for line_item in lines_to_fulfill:
                                line_item_id = uuid.UUID(str(line_item.get("item_id"))) if line_item.get("item_id") else None
                                line_wh_id = uuid.UUID(str(line_item.get("warehouse_id"))) if line_item.get("warehouse_id") else None
                                line_qty = Decimal(str(line_item.get("quantity", 0)))
                                if not line_item_id or not line_wh_id or line_qty <= 0:
                                    return {
                                        "delivery_note_number": None,
                                        "invoice_number": None,
                                        "general_ledger_status": "HOLD_INVALID_ORDER_LINES",
                                        "fulfillment_status": "FULFILLMENT_HELD",
                                        "shortage_reason": "Each fulfillment line needs a catalog item, warehouse, and positive quantity.",
                                    }
                                unit_price = Decimal(str(line_item.get("unit_price", 0)))
                                persisted_unit_price = order_price_by_item.get(line_item_id)
                                if not persisted_unit_price or unit_price != persisted_unit_price:
                                    return {
                                        "delivery_note_number": None,
                                        "invoice_number": None,
                                        "general_ledger_status": "HOLD_ORDER_PRICE_MISMATCH",
                                        "fulfillment_status": "FULFILLMENT_HELD",
                                        "shortage_reason": "Fulfillment price differs from the persisted sales order.",
                                    }
                                requested_qty_by_item[line_item_id] = (
                                    requested_qty_by_item.get(line_item_id, Decimal("0.0000")) + line_qty
                                )
                                computed_total += line_qty * persisted_unit_price
                                stock = (await s.execute(
                                    select(StockLevel).where(
                                        StockLevel.tenant_id == tenant_uuid,
                                        StockLevel.item_id == line_item_id,
                                        StockLevel.warehouse_id == line_wh_id,
                                    ).with_for_update()
                                )).scalar_one_or_none()
                                if not stock or stock.available_qty < line_qty or stock.current_qty < line_qty:
                                    return {
                                        "delivery_note_number": None,
                                        "invoice_number": None,
                                        "general_ledger_status": "HOLD_PENDING_STOCK_REPLENISHMENT",
                                        "fulfillment_status": "SHORTAGE_BACKORDER_HELD",
                                        "shortage_reason": f"Insufficient current available stock for item {line_item_id}.",
                                    }
                                locked_stock[(line_item_id, line_wh_id)] = stock

                            if not order_lines or requested_qty_by_item != ordered_qty_by_item:
                                return {
                                    "delivery_note_number": None,
                                    "invoice_number": None,
                                    "general_ledger_status": "HOLD_ORDER_LINE_MISMATCH",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": "Fulfillment lines do not match positive quantities on the tenant's sales order.",
                                }
                            if order.total_amount <= 0 or computed_total <= 0 or computed_total != order.total_amount:
                                return {
                                    "delivery_note_number": None,
                                    "invoice_number": None,
                                    "general_ledger_status": "HOLD_INVALID_ORDER_TOTAL",
                                    "fulfillment_status": "FULFILLMENT_HELD",
                                    "shortage_reason": "The persisted sales order has no positive total to invoice.",
                                }

                            # 1. Delivery Note
                            dn_num = f"DN-{order_num}"
                            dn = DeliveryNote(
                                tenant_id=tenant_uuid,
                                delivery_note_number=dn_num,
                                order_id=order_uuid,
                                customer_id=cust_uuid,
                                delivery_date=date.today(),
                                status="COMPLETED",
                            )
                            s.add(dn)
                            await s.flush()

                            total_amt = Decimal("0.0000")
                            delivery_items = []

                            if raw_items:
                                for it_dict in raw_items:
                                    it_id_s = it_dict.get("item_id")
                                    it_uuid = uuid.UUID(it_id_s) if it_id_s else None
                                    it_wh_s = it_dict.get("warehouse_id")
                                    it_wh_uuid = uuid.UUID(it_wh_s) if it_wh_s else wh_uuid
                                    it_qty = Decimal(str(it_dict.get("quantity", 1.0)))
                                    it_unit_price = Decimal(str(it_dict.get("unit_price", 0.0)))
                                    it_line_total = it_qty * it_unit_price
                                    total_amt += it_line_total

                                    if it_uuid:
                                        dn_item = DeliveryNoteItem(
                                            tenant_id=tenant_uuid,
                                            delivery_note_id=dn.delivery_note_id,
                                            item_id=it_uuid,
                                            warehouse_id=it_wh_uuid,
                                            quantity=it_qty,
                                        )
                                        s.add(dn_item)

                                        # Deduct on-hand stock
                                        stk = locked_stock[(it_uuid, it_wh_uuid)]
                                        actual_wh_uuid = stk.warehouse_id
                                        dn_item.warehouse_id = actual_wh_uuid
                                        stk.current_qty -= it_qty
                                        stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - it_qty)
                                        stk.available_qty = stk.current_qty - stk.reserved_qty
                                        rate = stk.valuation_rate
                                        qty_after = stk.current_qty

                                        sle = StockLedgerEntry(
                                            tenant_id=tenant_uuid,
                                            posting_datetime=datetime.now(UTC),
                                            item_id=it_uuid,
                                            warehouse_id=actual_wh_uuid,
                                            actual_qty=-it_qty,
                                            qty_after_transaction=qty_after,
                                            valuation_rate=rate,
                                            stock_value_difference=-it_qty * rate,
                                            source_document_type="DELIVERY_NOTE",
                                            source_document_id=dn.delivery_note_id,
                                        )
                                        s.add(sle)
                                        delivery_items.append({
                                            "item_id": str(it_uuid),
                                            "quantity": float(it_qty),
                                            "unit_price": float(it_unit_price),
                                            "line_total": float(it_line_total),
                                        })
                            else:
                                if item_uuid and wh_uuid:
                                    dn_item = DeliveryNoteItem(
                                        tenant_id=tenant_uuid,
                                        delivery_note_id=dn.delivery_note_id,
                                        item_id=item_uuid,
                                        warehouse_id=wh_uuid,
                                        quantity=qty,
                                    )
                                    s.add(dn_item)

                                    stk = locked_stock[(item_uuid, wh_uuid)]
                                    stk.current_qty -= qty
                                    stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - qty)
                                    stk.available_qty = stk.current_qty - stk.reserved_qty
                                    rate = stk.valuation_rate
                                    qty_after = stk.current_qty

                                    sle = StockLedgerEntry(
                                        tenant_id=tenant_uuid,
                                        posting_datetime=datetime.now(UTC),
                                        item_id=item_uuid,
                                        warehouse_id=wh_uuid,
                                        actual_qty=-qty,
                                        qty_after_transaction=qty_after,
                                        valuation_rate=rate,
                                        stock_value_difference=-qty * rate,
                                        source_document_type="DELIVERY_NOTE",
                                        source_document_id=dn.delivery_note_id,
                                    )
                                    s.add(sle)
                                total_amt = order.total_amount

                            # 2. Sales Invoice
                            inv_num = f"INV-{order_num.replace('SO-', '')}"
                            inv = SalesInvoice(
                                tenant_id=tenant_uuid,
                                invoice_number=inv_num,
                                customer_id=cust_uuid,
                                order_id=order_uuid,
                                delivery_note_id=dn.delivery_note_id,
                                invoice_date=date.today(),
                                due_date=date.today() + timedelta(days=customer.payment_terms_days),
                                currency=currency,
                                subtotal=total_amt,
                                tax_amount=Decimal("0.0000"),
                                total_amount=total_amt,
                                status="ISSUED",
                            )
                            s.add(inv)
                            await s.flush()

                            if raw_items:
                                for it_dict in raw_items:
                                    it_id_s = it_dict.get("item_id")
                                    it_uuid = uuid.UUID(it_id_s) if it_id_s else None
                                    it_qty = Decimal(str(it_dict.get("quantity", 1.0)))
                                    it_unit_price = Decimal(str(it_dict.get("unit_price", 0.0)))
                                    it_line_total = it_qty * it_unit_price

                                    if it_uuid:
                                        inv_item = SalesInvoiceItem(
                                            tenant_id=tenant_uuid,
                                            invoice_id=inv.invoice_id,
                                            item_id=it_uuid,
                                            quantity=it_qty,
                                            unit_price=it_unit_price,
                                            line_total=it_line_total,
                                        )
                                        s.add(inv_item)
                            else:
                                if item_uuid:
                                    inv_item = SalesInvoiceItem(
                                        tenant_id=tenant_uuid,
                                        invoice_id=inv.invoice_id,
                                        item_id=item_uuid,
                                        quantity=qty,
                                        unit_price=total_amt / max(qty, Decimal("1.0000")),
                                        line_total=total_amt,
                                    )
                                    s.add(inv_item)

                            # 3. Double-entry GL commit
                            entries = [
                                LedgerLineProposal(
                                    account_code=ar_account.account_code,
                                    cost_center=cost_center.cost_center_code,
                                    debit_amount=total_amt,
                                    credit_amount=Decimal("0.0000"),
                                    currency=currency,
                                ),
                                LedgerLineProposal(
                                    account_code=revenue_account.account_code,
                                    cost_center=cost_center.cost_center_code,
                                    debit_amount=Decimal("0.0000"),
                                    credit_amount=total_amt,
                                    currency=currency,
                                ),
                            ]
                            proposal = TransactionProposal(
                                tenant_id=tenant_uuid,
                                posting_date=date.today(),
                                currency=currency,
                                source_document_type="SALES_INVOICE",
                                source_document_id=inv.invoice_id,
                                entries=entries,
                                human_in_the_loop_approved=False,
                                agent_id="FINANCIAL_CONTROLLER",
                                verification_context={"invoice_number": inv_num, "order_number": order_num},
                            )
                            await ledger_engine.commit_transaction(session=s, proposal=proposal)
                            await s.commit()

                            res = {
                                "delivery_note_number": dn.delivery_note_number,
                                "invoice_number": inv.invoice_number,
                                "invoice_amount": float(total_amt),
                                "general_ledger_status": "COMMITTED_AR_AND_REVENUE",
                                "fulfillment_status": "DELIVERED_AND_INVOICED",
                                "gl_posted": True,
                            }
                else:
                    res = {"status": "SUCCESS", "node": node.name}

            elif node.agent_id == "PRODUCTION":
                raise PermissionError("Production capacity cannot be verified without tenant BOM operations and workstation data.")

            else:
                res = {"status": "SUCCESS", "node": node.name}

            node.output_result = res
            return res
        finally:
            chief_orchestrator.agent_states[node.agent_id] = AgentState.IDLE


dag_executor = DAGExecutor()
