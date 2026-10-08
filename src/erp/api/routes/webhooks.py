import asyncio
import logging
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep, require_roles
from erp.db.models.events import InboundEmailRecord
from erp.db.models.inventory import Item
from erp.db.models.sales import Customer, SalesOrder, SalesOrderItem
from erp.db.models.user import User
from erp.events.email_classifier import EmailIntent, classify_inbound_email
from erp.events.email_gateway import (
    EmailAttachment,
    IngestedEmailMessage,
    mailbox,
    outbound_mailer,
)
from erp.events.gmail_integration import gmail_service
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.persistence import persist_dag_snapshot
from erp.orchestration.worker import dag_executor
from erp.workflows.reconciliation.auto_clear import auto_clearing_engine
from erp.workflows.reconciliation.bank_feed_ingestor import bank_feed_ingestor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Inbound Webhooks & Email Gateways"])
controller_review_dep = require_roles("CONTROLLER")


class InboundEmailWebhookPayload(BaseModel):
    sender: str = Field(min_length=3, max_length=320)
    recipient: str = Field(default="rfq@company.internal", min_length=3, max_length=320)
    subject: str = Field(max_length=998)
    body_text: str = Field(max_length=100_000)
    attachments: list[str] = Field(default_factory=list, max_length=20)


class SendQuoteEmailRequest(BaseModel):
    recipient_email: str
    customer_name: str
    quote_number: str
    total_amount: float


class InboundEmailReviewRequest(BaseModel):
    decision: str = Field(pattern="^(ACCEPT_FOR_MANUAL_PROCESSING|REJECT)$")
    notes: str = Field(min_length=3, max_length=1000)


class ManualSalesOrderLine(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class CreateManualSalesOrderRequest(BaseModel):
    customer_id: uuid.UUID
    order_number: str = Field(min_length=2, max_length=64)
    delivery_date: date
    items: list[ManualSalesOrderLine] = Field(min_length=1, max_length=100)


class BankSettlementWebhookPayload(BaseModel):
    settlement_id: str = Field(default_factory=lambda: f"settle_{uuid.uuid4().hex[:8]}")
    amount: float
    currency: str = "USD"
    debtor_name: str
    debtor_account: str = "US-CHASE-0921"
    remittance_reference: str
    value_date: str = "2026-11-04"


@router.post("/email/inbound", summary="Ingest raw inbound email webhook (SendGrid/Postmark/SES)")
async def ingest_email_webhook(
    payload: InboundEmailWebhookPayload,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Records inbound mail, holds non-RFQ actions for review, and accepts explicit RFQs for evaluation."""
    classification = classify_inbound_email(
        sender=payload.sender,
        subject=payload.subject,
        body_text=payload.body_text,
        recipient=payload.recipient,
    )
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", payload.sender)
    cust_email = email_match.group(0) if email_match else payload.sender
    name_part = payload.sender.split("<")[0].strip().replace('"', "")
    cust_name = name_part if (name_part and "@" not in name_part) else "Enterprise Customer"

    # Filter out automated system notifications (Google alerts, noreply, security warnings)
    if classification.intent == EmailIntent.SYSTEM_NOTIFICATION:
        ingested = IngestedEmailMessage(
            sender=payload.sender,
            recipient=payload.recipient,
            subject=payload.subject,
            body_text=payload.body_text,
            attachments=[
                EmailAttachment(filename=att, content_type="application/octet-stream")
                for att in payload.attachments
            ],
            event_type=classification.event_type,
            tenant_id=str(tenant_id),
            status="FILTERED_NOTIFICATION",
            associated_dag_id=None,
        )
        await _persist_inbound_email(db, ingested)
        mailbox.add_inbox(ingested)
        return {
            "status": "FILTERED",
            "intent": classification.intent.value,
            "reason": classification.summary_reason,
            "event_type": classification.event_type,
            "message_id": ingested.message_id,
            "dag_id": None,
            "subtasks_spawned": 0,
        }

    # Orders, supplier invoices, and ambiguous inquiries must not enter the RFQ
    # quoting workflow. Hold them until a matching human-reviewed workflow exists.
    if classification.intent in {
        EmailIntent.CUSTOMER_ORDER,
        EmailIntent.SUPPLIER_INVOICE,
        EmailIntent.GENERAL_INQUIRY,
    }:
        ingested = IngestedEmailMessage(
            sender=payload.sender,
            recipient=payload.recipient,
            subject=payload.subject,
            body_text=payload.body_text,
            attachments=[
                EmailAttachment(filename=att, content_type="application/octet-stream")
                for att in payload.attachments
            ],
            event_type=classification.event_type,
            tenant_id=str(tenant_id),
            status="HUMAN_REVIEW_REQUIRED",
            associated_dag_id=None,
        )
        await _persist_inbound_email(db, ingested)
        mailbox.add_inbox(ingested)
        return {
            "status": "REQUIRES_REVIEW",
            "intent": classification.intent.value,
            "event_type": classification.event_type,
            "message_id": ingested.message_id,
            "dag_id": None,
            "subtasks_spawned": 0,
        }

    dag = chief_orchestrator.build_rfq_workflow_dag(
        tenant_id=tenant_id,
        rfq_payload={
            "customer_name": cust_name,
            "customer_email": cust_email,
            "sender": payload.sender,
            "inquiry_text": f"Subject: {payload.subject}\n\n{payload.body_text}",
            "attachments": payload.attachments,
        },
    )
    try:
        # The durable snapshot must exist before this request acknowledges work.
        await persist_dag_snapshot(dag)
    except Exception as exc:
        chief_orchestrator.active_dags.pop(dag.dag_id, None)
        logger.exception("Unable to persist inbound RFQ workflow")
        raise HTTPException(status_code=503, detail="Workflow could not be durably accepted.") from exc

    ingested = IngestedEmailMessage(
        sender=payload.sender,
        recipient=payload.recipient,
        subject=payload.subject,
        body_text=payload.body_text,
        attachments=[
            EmailAttachment(filename=att, content_type="application/octet-stream")
            for att in payload.attachments
        ],
        event_type=classification.event_type,
        tenant_id=str(tenant_id),
        status="DURABLY_ACCEPTED",
        associated_dag_id=dag.dag_id,
    )
    await _persist_inbound_email(db, ingested)
    mailbox.add_inbox(ingested)

    # Concurrent execution is safe to acknowledge only after durable acceptance.
    asyncio.create_task(dag_executor.execute_dag(dag))

    return {
        "status": "DURABLY_ACCEPTED",
        "intent": classification.intent.value,
        "event_type": classification.event_type,
        "message_id": ingested.message_id,
        "dag_id": dag.dag_id,
        "subtasks_spawned": len(dag.nodes),
    }


async def _persist_inbound_email(db, message: IngestedEmailMessage) -> None:
    """Commit tenant-scoped intake before acknowledging or queueing follow-up work."""
    try:
        record = InboundEmailRecord(
            message_id=message.message_id,
            tenant_id=uuid.UUID(message.tenant_id),
            sender=message.sender,
            recipient=message.recipient,
            subject=message.subject,
            body_text=message.body_text,
            attachment_names=[attachment.filename for attachment in message.attachments],
            event_type=message.event_type,
            status=message.status,
            associated_dag_id=message.associated_dag_id,
        )
        db.add(record)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


@router.get("/email/inbox", summary="Query received emails for tenant")
async def get_tenant_inbox(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns durable inbound email intake and review status for this tenant."""
    rows = (
        await db.execute(
            select(InboundEmailRecord)
            .where(InboundEmailRecord.tenant_id == tenant_id)
            .order_by(InboundEmailRecord.received_at.desc())
            .limit(100)
        )
    ).scalars().all()
    order_ids = [record.sales_order_id for record in rows if record.sales_order_id]
    order_statuses: dict[uuid.UUID, tuple[str, str | None]] = {}
    if order_ids:
        order_rows = (
            await db.execute(
                select(SalesOrder.order_id, SalesOrder.status, SalesOrder.fulfillment_warehouse_id).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.order_id.in_(order_ids),
                )
            )
        ).all()
        order_statuses = {order_id: (order_status, str(warehouse_id) if warehouse_id else None) for order_id, order_status, warehouse_id in order_rows}
    return [
        {
            "message_id": record.message_id,
            "sender": record.sender,
            "recipient": record.recipient,
            "subject": record.subject,
            "body_text": record.body_text,
            "attachments": [{"filename": name} for name in record.attachment_names],
            "event_type": record.event_type,
            "tenant_id": str(record.tenant_id),
            "status": record.status,
            "associated_dag_id": record.associated_dag_id,
            "sales_order_id": str(record.sales_order_id) if record.sales_order_id else None,
            "sales_order_status": order_statuses.get(record.sales_order_id, (None, None))[0] if record.sales_order_id else None,
            "fulfillment_warehouse_id": order_statuses.get(record.sales_order_id, (None, None))[1] if record.sales_order_id else None,
            "reviewed_by": str(record.reviewed_by) if record.reviewed_by else None,
            "review_notes": record.review_notes,
            "reviewed_at": record.reviewed_at,
            "created_at": record.received_at,
        }
        for record in rows
    ]


@router.post("/email/inbox/{message_id}/review", summary="Record a tenant reviewer decision for an inbound message")
async def review_inbound_email(
    message_id: str,
    payload: InboundEmailReviewRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reviewer: User = controller_review_dep,
):
    """Accept for manual handling or reject; this endpoint never creates an order or executes a workflow."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    record = (
        await db.execute(
            select(InboundEmailRecord)
            .where(
                InboundEmailRecord.message_id == message_id,
                InboundEmailRecord.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Inbound message not found.")
    if record.status != "HUMAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=409, detail="Inbound message is not awaiting review.")

    record.status = (
        "ACCEPTED_FOR_MANUAL_PROCESSING"
        if payload.decision == "ACCEPT_FOR_MANUAL_PROCESSING"
        else "REJECTED"
    )
    record.reviewed_by = reviewer.user_id
    record.review_notes = payload.notes
    record.reviewed_at = datetime.now(UTC)
    await db.flush()
    return {
        "message_id": record.message_id,
        "status": record.status,
        "reviewed_by": str(record.reviewed_by),
        "reviewed_at": record.reviewed_at,
        "review_notes": record.review_notes,
        "workflow_executed": False,
    }


@router.post("/email/inbox/{message_id}/sales-order", summary="Create a pending-confirmation sales order from a reviewed customer order")
async def create_manual_sales_order_from_email(
    message_id: str,
    payload: CreateManualSalesOrderRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    reviewer: User = controller_review_dep,
):
    """Creates a tenant-validated order draft; it does not reserve stock or start fulfillment."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    record = (
        await db.execute(
            select(InboundEmailRecord)
            .where(
                InboundEmailRecord.message_id == message_id,
                InboundEmailRecord.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Inbound message not found.")
    if record.event_type != "erp.crm.inbound_customer_order":
        raise HTTPException(status_code=409, detail="Only customer-order messages can create sales-order drafts.")
    if record.sales_order_id:
        return {
            "status": "PENDING_CONFIRMATION",
            "sales_order_id": str(record.sales_order_id),
            "message_id": record.message_id,
            "already_created": True,
            "stock_reserved": False,
            "fulfillment_started": False,
        }
    if record.status != "ACCEPTED_FOR_MANUAL_PROCESSING":
        raise HTTPException(status_code=409, detail="Accept this message for manual processing before creating an order draft.")

    customer = (
        await db.execute(
            select(Customer)
            .where(
                Customer.customer_id == payload.customer_id,
                Customer.tenant_id == tenant_id,
                Customer.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=422, detail="Customer must be active and belong to this tenant.")

    item_ids = [line.item_id for line in payload.items]
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(status_code=422, detail="Each item may appear only once; combine duplicate lines.")
    item_rows = (
        await db.execute(
            select(Item)
            .where(
                Item.tenant_id == tenant_id,
                Item.item_id.in_(item_ids),
                Item.is_active.is_(True),
                Item.is_sales_item.is_(True),
            )
            .with_for_update()
        )
    ).scalars().all()
    items_by_id = {item.item_id: item for item in item_rows}
    if set(items_by_id) != set(item_ids):
        raise HTTPException(status_code=422, detail="Every order item must be an active sales item owned by this tenant.")

    duplicate_number = (
        await db.execute(
            select(SalesOrder.order_id).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.order_number == payload.order_number,
            )
        )
    ).scalar_one_or_none()
    if duplicate_number:
        raise HTTPException(status_code=409, detail="That sales order number already exists for this tenant.")

    total_amount = sum(
        (line.quantity * line.unit_price for line in payload.items), Decimal("0.0000")
    )
    if total_amount <= 0 or total_amount >= Decimal("100000000000000"):
        raise HTTPException(status_code=422, detail="Order total is outside the supported monetary range.")
    order = SalesOrder(
        tenant_id=tenant_id,
        order_number=payload.order_number,
        customer_id=customer.customer_id,
        order_date=date.today(),
        delivery_date=payload.delivery_date,
        total_amount=total_amount,
        status="PENDING_CONFIRMATION",
    )
    db.add(order)
    await db.flush()
    for line in payload.items:
        db.add(
            SalesOrderItem(
                tenant_id=tenant_id,
                order_id=order.order_id,
                item_id=line.item_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.quantity * line.unit_price,
            )
        )
    record.sales_order_id = order.order_id
    record.status = "SALES_ORDER_DRAFT_CREATED"
    await db.flush()
    return {
        "status": order.status,
        "sales_order_id": str(order.order_id),
        "order_number": order.order_number,
        "message_id": record.message_id,
        "stock_reserved": False,
        "fulfillment_started": False,
    }


@router.get("/email/sent", summary="Query dispatched outbound emails for tenant")
async def get_tenant_sent(tenant_id: TenantIdDep):
    """Returns outbound email dispatch log (e.g. quote PDF deliveries)."""
    return mailbox.get_sent(str(tenant_id))


@router.post("/email/dispatch-quote", summary="Prepare quotation email for a configured delivery provider")
async def dispatch_quote_email(
    req: SendQuoteEmailRequest,
    tenant_id: TenantIdDep,
):
    """Stages a quotation email; no provider delivery is configured in this deployment."""
    msg = await outbound_mailer.dispatch_quote_email(
        recipient_email=req.recipient_email,
        customer_name=req.customer_name,
        quote_number=req.quote_number,
        total_amount=req.total_amount,
        tenant_id=str(tenant_id),
    )
    return {
        "status": msg.status,
        "dispatch_id": msg.dispatch_id,
        "recipient": msg.recipient,
    }


@router.post("/banking/settlement", summary="Open-Banking ISO 20022 / CAMT.053 Settlement Webhook")
async def ingest_banking_settlement(
    payload: BankSettlementWebhookPayload,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Receives live settlement notifications from open-banking rails and executes reconciliation against open receivables."""
    raw_tx = bank_feed_ingestor.parse_webhook_payload({
        "account_number": payload.debtor_account,
        "amount": payload.amount,
        "counterparty_name": payload.debtor_name,
        "remittance_information": payload.remittance_reference,
        "currency": payload.currency,
        "booking_date": payload.value_date,
    })

    result = await auto_clearing_engine.process_bank_transaction(
        session=db,
        tenant_id=tenant_id,
        tx=raw_tx,
    )

    action = "AUTO_MATCH_CONFIRMED" if result.is_auto_cleared else "MANUAL_REVIEW_STAGED"
    return {
        "settlement_id": payload.settlement_id,
        "status": "AUTO_MATCH_CONFIRMED" if result.is_auto_cleared else "UNMATCHED_STAGED",
        "amount": payload.amount,
        "counterparty": payload.debtor_name,
        "remittance_reference": payload.remittance_reference,
        "confidence": result.confidence_score,
        "action": action,
        "matched_document": result.matched_order_number,
        "transaction_id": str(result.ledger_commit.transaction_id) if result.ledger_commit else None,
    }



# ==============================================================================
# GMAIL OAUTH 2.0 INTEGRATION ENDPOINTS
# ==============================================================================


class GmailCallbackPayload(BaseModel):
    code: str
    redirect_uri: str = "http://localhost:3000/inbox"


class GmailCredentialsPayload(BaseModel):
    client_id: str
    client_secret: str


@router.get("/gmail/status", summary="Get Gmail OAuth connection status for tenant")
async def get_gmail_status(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns whether tenant has connected their corporate Gmail account and credentials configuration status."""
    conn = await gmail_service.get_connection_async(str(tenant_id), db)
    cred_status = gmail_service.get_credentials_status()
    return {
        "is_connected": conn.is_connected,
        "connected_email": conn.connected_email,
        "last_synced_at": conn.last_synced_at,
        "synced_messages_count": conn.synced_messages_count,
        "is_configured": cred_status["is_configured"],
        "client_id": cred_status["client_id"],
    }


@router.get("/gmail/credentials", summary="Check Google OAuth credentials configuration")
async def get_gmail_credentials():
    """Checks if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set."""
    return gmail_service.get_credentials_status()


@router.post("/gmail/credentials", summary="Save Google OAuth credentials")
async def set_gmail_credentials(payload: GmailCredentialsPayload):
    """Saves GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to environment and .env."""
    return gmail_service.save_credentials(payload.client_id, payload.client_secret)


@router.get("/gmail/authorize", summary="Generate Google OAuth 2.0 Authorization URL")
async def get_gmail_auth_url(tenant_id: TenantIdDep, redirect_uri: str | None = None):
    """Generates the official Google OAuth 2.0 consent URL for Gmail access."""
    return gmail_service.get_authorization_url(str(tenant_id), redirect_uri)


@router.post("/gmail/callback", summary="Exchange Google OAuth code for tokens")
async def handle_gmail_oauth_callback(
    payload: GmailCallbackPayload,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Exchanges Google authorization code for access/refresh tokens and stores connection."""
    try:
        conn = await gmail_service.exchange_code_for_tokens(
            tenant_id=str(tenant_id),
            code=payload.code,
            redirect_uri=payload.redirect_uri,
            session=db,
        )
        return {
            "status": "CONNECTED",
            "is_connected": conn.is_connected,
            "connected_email": conn.connected_email,
            "last_synced_at": conn.last_synced_at,
        }
    except Exception as e:
        logger.error("Failed Google OAuth callback token exchange: %s", e)
        raise HTTPException(status_code=400, detail="Gmail authorization could not be completed.") from e


@router.post("/gmail/disconnect", summary="Disconnect Gmail account")
async def disconnect_gmail(tenant_id: TenantIdDep, db: DbSessionDep):
    """Disconnects and revokes tenant's Gmail OAuth session in DB and memory."""
    await gmail_service.disconnect_async(str(tenant_id), db)
    return {"status": "DISCONNECTED"}


@router.post("/gmail/sync", summary="Trigger real-time Gmail inbox sync for RFQs")
async def sync_gmail_inbox(tenant_id: TenantIdDep, db: DbSessionDep):
    """Polls Gmail for unread emails, parses RFQs via BAML, and dispatches multi-agent DAGs."""
    try:
        synced = await gmail_service.sync_inbox(str(tenant_id), db)
        return {
            "status": "SYNCED",
            "messages_synced": len(synced),
            "messages": synced,
        }
    except Exception as e:
        logger.warning("Gmail sync error: %s", e)
        raise HTTPException(status_code=400, detail="Gmail inbox could not be synced.") from e
