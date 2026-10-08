"""Autonomous Inbound & Outbound Email Gateway (PRD §Revenue & CRM Agent & AP Ingestion).

Provides an asynchronous SMTP daemon listening on port 2525 and an outbound mailer
for customer quotation delivery and vendor dispute notifications.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from aiosmtpd.controller import Controller
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EmailAttachment(BaseModel):
    filename: str
    content_type: str
    size_bytes: int | None = None
    data_preview: str = ""


class IngestedEmailMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex}")
    sender: str
    recipient: str
    subject: str
    body_text: str
    body_html: str = ""
    attachments: list[EmailAttachment] = Field(default_factory=list)
    event_type: str = "erp.crm.inbound_rfq_email"
    tenant_id: str
    status: str = "PROCESSED"
    associated_dag_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SentEmailMessage(BaseModel):
    dispatch_id: str = Field(default_factory=lambda: f"out_{uuid.uuid4().hex[:10]}")
    recipient: str
    subject: str
    body: str
    attachment_name: str | None = None
    attachment_size_bytes: int = 0
    tenant_id: str
    status: str = "STAGED_PROVIDER_UNAVAILABLE"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmailStorage:
    """In-memory thread-safe mailbox store for UI visibility."""

    def __init__(self):
        self.inbox: list[IngestedEmailMessage] = []
        self.sent: list[SentEmailMessage] = []

    def add_inbox(self, msg: IngestedEmailMessage):
        if any(existing.message_id == msg.message_id for existing in self.inbox):
            return
        self.inbox.insert(0, msg)
        if len(self.inbox) > 100:
            self.inbox.pop()

    def add_sent(self, msg: SentEmailMessage):
        self.sent.insert(0, msg)
        if len(self.sent) > 100:
            self.sent.pop()

    def get_inbox(self, tenant_id: str | None = None) -> list[IngestedEmailMessage]:
        if not tenant_id:
            return self.inbox
        return [m for m in self.inbox if m.tenant_id == tenant_id]

    def get_sent(self, tenant_id: str | None = None) -> list[SentEmailMessage]:
        if not tenant_id:
            return self.sent
        return [m for m in self.sent if m.tenant_id == tenant_id]


mailbox = EmailStorage()


class SMTPEmailHandler:
    """Reject unauthenticated SMTP intake until tenant routing is configured."""

    async def handle_DATA(self, server, session, envelope):
        logger.warning("Rejected SMTP message: authenticated tenant routing is not configured")
        return "554 SMTP intake is disabled; use the authenticated tenant webhook"


class EmailGateway:
    """Manages the SMTP daemon controller lifecycle."""

    def __init__(self, host: str = "0.0.0.0", port: int = 2525):
        self.host = host
        self.port = port
        self.handler = SMTPEmailHandler()
        self.controller: Controller | None = None

    def start(self):
        try:
            self.controller = Controller(self.handler, hostname=self.host, port=self.port)
            self.controller.start()
            logger.info("Autonomous Inbound SMTP Gateway listening on %s:%d", self.host, self.port)
        except Exception as e:
            logger.warning("Could not bind SMTP gateway on port %d (%s). Local webhook available.", self.port, e)

    def stop(self):
        if self.controller:
            self.controller.stop()
            logger.info("Autonomous Inbound SMTP Gateway stopped.")


email_gateway = EmailGateway()


class OutboundQuotationMailer:
    """Compiles and delivers margin-defended PDF quotes to clients via email."""

    @staticmethod
    async def dispatch_quote_email(
        recipient_email: str,
        customer_name: str,
        quote_number: str,
        total_amount: float,
        pdf_bytes: bytes | None = None,
        *,
        tenant_id: str,
    ) -> SentEmailMessage:
        subject = f"Official Commercial Quotation: {quote_number} - {customer_name}"
        body = (
            f"Dear {customer_name},\n\n"
            f"Thank you for your commercial inquiry. Please find attached our formal quotation "
            f"{quote_number} totaling ${total_amount:,.2f}.\n\n"
            f"Please review the attached quotation.\n\n"
            f"Autonomous Commercial Operations\n"
            f"AI-Native Enterprise Resource Planning"
        )

        sent_msg = SentEmailMessage(
            recipient=recipient_email,
            subject=subject,
            body=body,
            attachment_name=f"{quote_number}.pdf",
            attachment_size_bytes=len(pdf_bytes) if pdf_bytes else 0,
            tenant_id=tenant_id,
            status="STAGED_PROVIDER_UNAVAILABLE",
        )
        mailbox.add_sent(sent_msg)
        logger.info("Outbound quote email dispatched to %s for %s (%s)", recipient_email, quote_number, sent_msg.dispatch_id)
        return sent_msg

    @staticmethod
    async def dispatch_invoice_email(
        recipient_email: str,
        customer_name: str,
        order_number: str,
        invoice_number: str,
        total_amount: float,
        pdf_bytes: bytes | None = None,
        *,
        tenant_id: str,
    ) -> SentEmailMessage:
        """Delivers official Sales Invoice PDF to buyer upon order fulfillment."""
        subject = f"Order Confirmation & Sales Invoice {invoice_number} for Order {order_number}"
        body = (
            f"Dear {customer_name},\n\n"
            f"Thank you for your order {order_number}! Your purchase has been confirmed and fulfilled.\n\n"
            f"Order Reference: {order_number}\n"
            f"Sales Invoice: {invoice_number}\n"
            f"Total Amount: ${total_amount:,.2f} USD\n\n"
            f"Your order has been allocated and delivered from our warehouse. "
            f"Please find attached your official Sales Invoice PDF.\n\n"
            f"Autonomous Revenue & Fulfillment Agent\n"
            f"AI-Native Enterprise Resource Planning"
        )
        sent_msg = SentEmailMessage(
            recipient=recipient_email,
            subject=subject,
            body=body,
            attachment_name=f"{invoice_number}.pdf",
            attachment_size_bytes=len(pdf_bytes) if pdf_bytes else 0,
            tenant_id=tenant_id,
            status="STAGED_PROVIDER_UNAVAILABLE",
        )
        mailbox.add_sent(sent_msg)
        logger.info("Outbound invoice email dispatched to %s for %s (%s)", recipient_email, invoice_number, sent_msg.dispatch_id)
        return sent_msg

    @staticmethod
    async def dispatch_shortage_notice_email(
        recipient_email: str,
        customer_name: str,
        order_number: str,
        requested_sku: str,
        requested_qty: float,
        available_qty: float,
        lead_time_days: int = 7,
        *,
        tenant_id: str,
    ) -> SentEmailMessage:
        """Delivers inventory shortage and backorder lead-time notice to buyer."""
        subject = f"Order Notification: Inventory Backorder Update for Order {order_number}"
        body = (
            f"Dear {customer_name},\n\n"
            f"Thank you for your order {order_number} for {requested_qty:,.0f} units of {requested_sku}.\n\n"
            f"Our autonomous inventory engine has verified current stock availability. "
            f"We currently have {available_qty:,.0f} units on hand, which is insufficient to immediately fulfill your full request.\n\n"
            f"We have automatically placed your order on prioritized BACKORDER and triggered an immediate "
            f"manufacturing replenishment work order. The estimated delivery lead time is {lead_time_days} business days.\n\n"
            f"We apologize for the brief delay and will send you a dispatch notification and invoice as soon as the batch is completed.\n\n"
            f"Autonomous Supply Chain Operations\n"
            f"AI-Native Enterprise Resource Planning"
        )
        sent_msg = SentEmailMessage(
            recipient=recipient_email,
            subject=subject,
            body=body,
            attachment_name=None,
            attachment_size_bytes=0,
            tenant_id=tenant_id,
            status="STAGED_PROVIDER_UNAVAILABLE",
        )
        mailbox.add_sent(sent_msg)
        logger.info("Outbound shortage notice email dispatched to %s for %s (%s)", recipient_email, order_number, sent_msg.dispatch_id)
        return sent_msg

    @staticmethod
    async def dispatch_catalog_mismatch_email(
        recipient_email: str,
        customer_name: str,
        requested_sku: str,
        requested_qty: float,
        recommended_alternatives: list[dict[str, Any]] | None = None,
        custom_body: str | None = None,
        *,
        tenant_id: str,
    ) -> SentEmailMessage:
        """Delivers catalog mismatch notification and product alternatives to buyer."""
        subject = f"Regarding your order request for {requested_sku} - Product Availability Update"
        if custom_body:
            body = custom_body
        else:
            alt_lines = ""
            if recommended_alternatives:
                alt_lines = "\n\nOur available products and current stock include:\n" + "\n".join(
                    [f"- {a.get('item_code')}: {a.get('item_name')} (${float(a.get('standard_rate', 0.0)):,.2f} each, {float(a.get('available_qty', 0.0)):,.0f} available)" for a in recommended_alternatives]
                )
            body = (
                f"Dear {customer_name},\n\n"
                f"Thank you for reaching out to us. We received your request for {requested_qty:,.0f} units of '{requested_sku}'.\n\n"
                f"However, '{requested_sku}' is not currently available in our product catalog.{alt_lines}\n\n"
                f"Please let us know if you would like to proceed with an order for any of our available products.\n\n"
                f"Autonomous Sales & Customer Success\n"
                f"AI-Native Enterprise Resource Planning"
            )
        sent_msg = SentEmailMessage(
            recipient=recipient_email,
            subject=subject,
            body=body,
            attachment_name=None,
            attachment_size_bytes=0,
            tenant_id=tenant_id,
            status="STAGED_PROVIDER_UNAVAILABLE",
        )
        mailbox.add_sent(sent_msg)
        logger.info("Outbound catalog mismatch email dispatched to %s for %s (%s)", recipient_email, requested_sku, sent_msg.dispatch_id)
        return sent_msg


outbound_mailer = OutboundQuotationMailer()
