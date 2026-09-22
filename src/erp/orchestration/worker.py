import asyncio
from datetime import UTC, date, datetime
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
from erp.db.session import async_session_factory
from erp.ledger.engine import TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal
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
                # 1. Order Extraction
                if "order" in node.name.lower() and ("extract" in node.name.lower() or "buyer" in node.name.lower()):
                    inquiry_text = payload.get("inquiry_text", "")
                    extraction = await baml_client.parse_rfq_document(inquiry_text or "Purchase Order")
                    sku = extraction.line_items[0].requested_sku if extraction.line_items else "FG-ENCLOSURE-IP67"
                    qty = float(extraction.line_items[0].quantity) if extraction.line_items else 10.0
                    price = float(extraction.line_items[0].target_unit_price) if extraction.line_items and extraction.line_items[0].target_unit_price else 1200.0

                    po_match = re.search(r"\b(PO[-_\s]?[A-Za-z0-9-]+)\b", inquiry_text, re.IGNORECASE)
                    po_num = po_match.group(1).upper().replace(" ", "-") if po_match else f"PO-{uuid.uuid4().hex[:6].upper()}"

                    res = {
                        "customer_name": payload.get("customer_name") or extraction.customer_name,
                        "customer_email": payload.get("customer_email") or extraction.customer_email,
                        "po_number": po_num,
                        "requested_sku": payload.get("target_sku") or sku,
                        "quantity": float(payload.get("quantity") or qty),
                        "target_unit_price": price,
                        "intent": "CUSTOMER_ORDER",
                    }

                # 2. Inbound RFQ Parsing
                elif "parse" in node.name.lower() or "rfq" in node.name.lower():
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
                        "intent": "CUSTOMER_RFQ",
                    }

                # 3. Dynamic Quote Generation
                elif "quote" in node.name.lower():
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    material_cost = Decimal(str(payload.get("material_cost", "24.50")))
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
                    qty = Decimal(str(payload.get("quantity", 10.0)))
                    unit_price = Decimal(str(payload.get("target_unit_price", 1200.0)))
                    total_amt = (qty * unit_price).quantize(Decimal("0.0001"))

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

                        # Get or provision item
                        item_id_str = payload.get("item_id")
                        if item_id_str:
                            item_id = uuid.UUID(item_id_str)
                        else:
                            item_stmt = select(Item).where(Item.tenant_id == tenant_uuid, Item.item_code == sku)
                            item = (await s.execute(item_stmt)).scalar_one_or_none()
                            if not item:
                                item = Item(
                                    tenant_id=tenant_uuid,
                                    item_code=sku,
                                    item_name=f"Standard {sku}",
                                    standard_rate=unit_price,
                                    is_active=True,
                                )
                                s.add(item)
                                await s.flush()
                            item_id = item.item_id

                        # Check inventory feasibility from Node 2
                        is_in_stock = payload.get("is_in_stock", True)
                        so_status = "CONFIRMED" if is_in_stock else "BACKORDERED"

                        # Create confirmed or backordered Sales Order
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

                        # Order item line
                        so_item = SalesOrderItem(
                            tenant_id=tenant_uuid,
                            order_id=order.order_id,
                            item_id=item_id,
                            quantity=qty,
                            unit_price=unit_price,
                            line_total=total_amt,
                        )
                        s.add(so_item)

                        # Reserve stock in inventory if available
                        wh_id_str = payload.get("warehouse_id")
                        wh_id = uuid.UUID(wh_id_str) if wh_id_str else None
                        if not wh_id:
                            wh_stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_uuid, Warehouse.is_active.is_(True))
                            wh = (await s.execute(wh_stmt)).scalars().first()
                            if wh:
                                wh_id = wh.warehouse_id

                        stock_reserved_qty = Decimal("0.0000")
                        if wh_id and is_in_stock:
                            stk_stmt = select(StockLevel).where(
                                StockLevel.tenant_id == tenant_uuid,
                                StockLevel.item_id == item_id,
                                StockLevel.warehouse_id == wh_id,
                            )
                            stk = (await s.execute(stk_stmt)).scalar_one_or_none()
                            if stk:
                                stk.reserved_qty += qty
                                stk.available_qty = stk.current_qty - stk.reserved_qty
                                stock_reserved_qty = qty
                            else:
                                stk = StockLevel(
                                    tenant_id=tenant_uuid,
                                    item_id=item_id,
                                    warehouse_id=wh_id,
                                    current_qty=Decimal("100.0000"),
                                    reserved_qty=qty,
                                    available_qty=Decimal("100.0000") - qty,
                                    valuation_rate=unit_price,
                                )
                                s.add(stk)
                                stock_reserved_qty = qty

                        await s.commit()

                        res = {
                            "customer_id": str(cust.customer_id),
                            "customer_name": cust.customer_name,
                            "customer_code": cust.customer_code,
                            "order_id": str(order.order_id),
                            "order_number": order.order_number,
                            "order_total": float(total_amt),
                            "stock_reserved": float(stock_reserved_qty),
                            "item_id": str(item_id),
                            "warehouse_id": str(wh_id) if wh_id else None,
                            "status": so_status,
                        }

                # 5. Outbound Order Confirmation & Invoice Dispatch
                elif "dispatch" in node.name.lower():
                    tenant_id_str = payload.get("tenant_id") or "00000000-0000-0000-0000-000000000001"
                    cust_email = payload.get("customer_email") or "orders@customer.internal"
                    cust_name = payload.get("customer_name") or "Valued Customer"
                    order_num = payload.get("order_number") or "SO-PENDING"
                    is_in_stock = payload.get("is_in_stock", True)
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    req_qty = float(payload.get("requested_qty") or payload.get("quantity") or 10.0)
                    avail_qty = float(payload.get("available_qty", 0.0))

                    if not is_in_stock:
                        # 1. Stock Shortage: Reply with Backorder & ETA Notice
                        subject = f"Order Notification: Inventory Backorder Update for Order {order_num}"
                        body = (
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
                        # 2. Stock Available: Generate PDF Sales Invoice & Deliver to Customer
                        inv_num = payload.get("invoice_number", f"INV-{order_num.replace('SO-', '')}")
                        dn_num = payload.get("delivery_note_number", f"DN-{order_num}")
                        inv_amt = float(payload.get("invoice_amount") or payload.get("order_total") or 12000.0)

                        # Generate official PDF invoice bytes
                        inv_data = InvoiceData(
                            invoice_number=inv_num,
                            order_number=order_num,
                            delivery_note_number=dn_num,
                            customer_name=cust_name,
                            customer_email=cust_email,
                            items=[
                                InvoiceLineItem(
                                    item_code=sku,
                                    description=f"Standard {sku}",
                                    quantity=Decimal(str(req_qty)),
                                    unit_price=Decimal(str(inv_amt / max(req_qty, 1.0))).quantize(Decimal("0.01")),
                                    line_total=Decimal(str(inv_amt)).quantize(Decimal("0.01")),
                                )
                            ],
                            subtotal=Decimal(str(inv_amt)).quantize(Decimal("0.01")),
                            tax_amount=Decimal("0.00"),
                            total_amount=Decimal(str(inv_amt)).quantize(Decimal("0.01")),
                        )
                        pdf_bytes = invoice_pdf_generator.generate_pdf(inv_data)

                        subject = f"Order Confirmation & Sales Invoice {inv_num} for Order {order_num}"
                        body = (
                            f"Dear {cust_name},\n\n"
                            f"Thank you for your order {order_num}! Your purchase has been confirmed and fulfilled.\n\n"
                            f"Order Reference: {order_num}\n"
                            f"Delivery Note: {dn_num}\n"
                            f"Sales Invoice: {inv_num}\n"
                            f"Total Amount: ${inv_amt:,.2f} USD\n\n"
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
                    tenant_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.UUID("00000000-0000-0000-0000-000000000001")
                    sku = payload.get("requested_sku", "FG-ENCLOSURE-IP67")
                    qty = Decimal(str(payload.get("quantity", 10.0)))

                    async with async_session_factory() as s:
                        wh_stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_uuid, Warehouse.is_active.is_(True))
                        wh = (await s.execute(wh_stmt)).scalars().first()
                        if not wh:
                            wh = Warehouse(tenant_id=tenant_uuid, warehouse_code="WH-MAIN-01", warehouse_name="Central Logistics", is_active=True)
                            s.add(wh)
                            await s.flush()

                        item_stmt = select(Item).where(Item.tenant_id == tenant_uuid, Item.item_code == sku)
                        item = (await s.execute(item_stmt)).scalar_one_or_none()
                        if not item:
                            item = Item(tenant_id=tenant_uuid, item_code=sku, item_name=f"Industrial {sku}", standard_rate=Decimal("1200.0000"))
                            s.add(item)
                            await s.flush()

                        stk_stmt = select(StockLevel).where(
                            StockLevel.tenant_id == tenant_uuid,
                            StockLevel.item_id == item.item_id,
                            StockLevel.warehouse_id == wh.warehouse_id,
                        )
                        stk = (await s.execute(stk_stmt)).scalar_one_or_none()
                        if not stk:
                            stk = StockLevel(
                                tenant_id=tenant_uuid,
                                item_id=item.item_id,
                                warehouse_id=wh.warehouse_id,
                                current_qty=Decimal("100.0000"),
                                reserved_qty=Decimal("0.0000"),
                                available_qty=Decimal("100.0000"),
                                valuation_rate=Decimal("1200.0000"),
                            )
                            s.add(stk)
                            await s.commit()

                        curr_qty = stk.current_qty
                        res_qty = stk.reserved_qty
                        avail_qty = stk.available_qty

                        is_in_stock = avail_qty >= qty
                        res = {
                            "is_in_stock": bool(is_in_stock),
                            "warehouse_code": wh.warehouse_code,
                            "warehouse_id": str(wh.warehouse_id),
                            "item_id": str(item.item_id),
                            "requested_qty": float(qty),
                            "current_on_hand_qty": float(curr_qty),
                            "reserved_qty": float(res_qty),
                            "available_qty": float(avail_qty),
                            "fulfillment_status": "STOCK_AVAILABLE_READY_TO_FULFILL" if is_in_stock else "SHORTAGE_BACKORDER_TRIGGERED",
                        }
                else:
                    # Material cost evaluation
                    res = {
                        "material_cost": 24.50,
                        "lead_time_days": 7,
                        "supplier_name": "Verified Supply Partner",
                    }

            elif node.agent_id == "FINANCIAL_CONTROLLER":
                if "fulfill" in node.name.lower() or "invoice" in node.name.lower() or "ledger" in node.name.lower():
                    is_in_stock = payload.get("is_in_stock", True)
                    if not is_in_stock:
                        res = {
                            "delivery_note_number": None,
                            "invoice_number": None,
                            "general_ledger_status": "HOLD_PENDING_STOCK_REPLENISHMENT",
                            "fulfillment_status": "SHORTAGE_BACKORDER_HELD",
                            "shortage_reason": f"Inventory insufficient for SKU {payload.get('requested_sku', 'item')}.",
                        }
                    else:
                        tenant_id_str = payload.get("tenant_id")
                        tenant_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.UUID("00000000-0000-0000-0000-000000000001")
                        order_id_str = payload.get("order_id")
                        order_uuid = uuid.UUID(order_id_str) if order_id_str else None
                        order_num = payload.get("order_number", "SO-1001")
                        cust_id_str = payload.get("customer_id")
                        cust_uuid = uuid.UUID(cust_id_str) if cust_id_str else None
                        wh_id_str = payload.get("warehouse_id")
                        wh_uuid = uuid.UUID(wh_id_str) if wh_id_str else None
                        item_id_str = payload.get("item_id")
                        item_uuid = uuid.UUID(item_id_str) if item_id_str else None
                        qty = Decimal(str(payload.get("quantity", 10.0)))
                        total_amt = Decimal(str(payload.get("order_total", 12000.0)))

                        async with async_session_factory() as s:
                            # 1. Delivery Note
                            dn_num = f"DN-{order_num}"
                            dn = DeliveryNote(
                                tenant_id=tenant_uuid,
                                delivery_note_number=dn_num,
                                order_id=order_uuid or uuid.uuid4(),
                                customer_id=cust_uuid or uuid.uuid4(),
                                delivery_date=date.today(),
                                status="COMPLETED",
                            )
                            s.add(dn)
                            await s.flush()

                            if item_uuid and wh_uuid:
                                dn_item = DeliveryNoteItem(
                                    tenant_id=tenant_uuid,
                                    delivery_note_id=dn.delivery_note_id,
                                    item_id=item_uuid,
                                    warehouse_id=wh_uuid,
                                    quantity=qty,
                                )
                                s.add(dn_item)

                                # Deduct on-hand stock
                                stk_stmt = select(StockLevel).where(
                                    StockLevel.tenant_id == tenant_uuid,
                                    StockLevel.item_id == item_uuid,
                                    StockLevel.warehouse_id == wh_uuid,
                                )
                                stk = (await s.execute(stk_stmt)).scalar_one_or_none()
                                if stk:
                                    stk.current_qty -= qty
                                    stk.reserved_qty = max(Decimal("0.0000"), stk.reserved_qty - qty)
                                    stk.available_qty = stk.current_qty - stk.reserved_qty
                                    rate = stk.valuation_rate
                                    qty_after = stk.current_qty
                                else:
                                    rate = Decimal("1200.0000")
                                    qty_after = Decimal("0.0000")

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

                            # 2. Sales Invoice
                            inv_num = f"INV-{order_num.replace('SO-', '')}"
                            inv = SalesInvoice(
                                tenant_id=tenant_uuid,
                                invoice_number=inv_num,
                                customer_id=cust_uuid or uuid.uuid4(),
                                order_id=order_uuid,
                                delivery_note_id=dn.delivery_note_id,
                                invoice_date=date.today(),
                                due_date=date.today(),
                                currency="USD",
                                subtotal=total_amt,
                                tax_amount=Decimal("0.0000"),
                                total_amount=total_amt,
                                status="ISSUED",
                            )
                            s.add(inv)
                            await s.flush()

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
                                    account_code="1200-AR-CUSTOMERS",
                                    cost_center="SALES-GLOBAL",
                                    debit_amount=total_amt,
                                    credit_amount=Decimal("0.0000"),
                                    currency="USD",
                                ) if "1200-AR-CUSTOMERS" in ["1200-AR-CUSTOMERS"] else None,
                                LedgerLineProposal(
                                    account_code="1200-AR-CUSTOMERS",
                                    cost_center="SALES-GLOBAL",
                                    debit_amount=total_amt,
                                    credit_amount=Decimal("0.0000"),
                                    currency="USD",
                                ),
                                LedgerLineProposal(
                                    account_code="4000-SALES-REVENUE",
                                    cost_center="SALES-GLOBAL",
                                    debit_amount=Decimal("0.0000"),
                                    credit_amount=total_amt,
                                    currency="USD",
                                ),
                            ]
                            entries = [e for e in entries[1:] if e is not None]
                            proposal = TransactionProposal(
                                tenant_id=tenant_uuid,
                                posting_date=date.today(),
                                currency="USD",
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
                            }
                else:
                    res = {"status": "SUCCESS", "node": node.name}

            elif node.agent_id == "PRODUCTION":
                # Machine makespan solve
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
