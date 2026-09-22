"""Inbound Email Intent Classification and Filtering Engine."""

from enum import StrEnum
from pydantic import BaseModel


class EmailIntent(StrEnum):
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"
    CUSTOMER_ORDER = "CUSTOMER_ORDER"
    CUSTOMER_RFQ = "CUSTOMER_RFQ"
    SUPPLIER_INVOICE = "SUPPLIER_INVOICE"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"


class EmailClassificationResult(BaseModel):
    intent: EmailIntent
    event_type: str
    is_commercial_actionable: bool
    confidence: float
    detected_keywords: list[str] = []
    summary_reason: str


def classify_inbound_email(
    sender: str,
    subject: str,
    body_text: str,
    recipient: str = "",
) -> EmailClassificationResult:
    """Classifies an incoming email into system alerts, commercial customer orders, RFQs, or supplier invoices."""
    sender_lower = (sender or "").lower()
    subject_lower = (subject or "").lower()
    body_lower = (body_text or "").lower()
    combined_text = f"{subject_lower} {body_lower}"

    # 1. Detect System Alerts, Automated Notifications, and Security Emails
    system_sender_patterns = [
        "no-reply", "noreply", "mailer-daemon", "accounts.google.com",
        "notifications@", "security@", "donotreply", "system@", "alert@"
    ]
    system_text_patterns = [
        "security alert", "allowed access to", "verify your email",
        "confirm your email", "password reset", "two-factor", "sign-in attempt",
        "account recovery", "automatic reply", "out of office", "unsubscribe",
        "newsletter", "privacy policy update", "terms of service", "suspicious activity",
        "access to some of your google account"
    ]

    is_system_sender = any(p in sender_lower for p in system_sender_patterns)
    is_system_content = any(p in combined_text for p in system_text_patterns)

    if is_system_sender or is_system_content:
        return EmailClassificationResult(
            intent=EmailIntent.SYSTEM_NOTIFICATION,
            event_type="erp.communication.system_notification",
            is_commercial_actionable=False,
            confidence=0.99,
            detected_keywords=[p for p in system_text_patterns if p in combined_text] or ["automated_system_sender"],
            summary_reason="Identified automated system, authentication, or security notification. Bypassing commercial transaction pipeline.",
        )

    # 2. Detect Supplier Invoices & Bills
    invoice_keywords = [
        "invoice", "bill", "billing statement", "remittance advice",
        "payment due", "amount due", "vendor invoice", "tax invoice"
    ]
    matched_inv_keywords = [k for k in invoice_keywords if k in combined_text]
    if matched_inv_keywords:
        return EmailClassificationResult(
            intent=EmailIntent.SUPPLIER_INVOICE,
            event_type="erp.supplychain.invoice_received",
            is_commercial_actionable=True,
            confidence=0.95,
            detected_keywords=matched_inv_keywords,
            summary_reason="Supplier invoice or AP billing statement detected.",
        )

    # 3. Detect Customer Purchase Orders (Firm Orders)
    order_keywords = [
        "purchase order", "po#", "po-", "po ", "p.o.", "order confirmation",
        "place an order", "placing an order", "we order", "order for", "firm order",
        "accept quote", "accept quotation", "accept the quote", "proceed with order",
        "attached purchase order", "please deliver", "please process our order",
        "confirming order", "order dispatch", "buying", "confirm order", "order attached"
    ]
    matched_order_keywords = [k for k in order_keywords if k in combined_text]
    if matched_order_keywords:
        return EmailClassificationResult(
            intent=EmailIntent.CUSTOMER_ORDER,
            event_type="erp.crm.inbound_customer_order",
            is_commercial_actionable=True,
            confidence=0.96,
            detected_keywords=matched_order_keywords,
            summary_reason="Customer Purchase Order or firm commercial order commitment detected.",
        )

    # 4. Detect Customer RFQs / Inquiries
    rfq_keywords = [
        "rfq", "request for quote", "request for quotation", "quote",
        "quotation", "price inquiry", "pricing for", "how much for",
        "can you quote", "cost estimate", "inquire about price", "lead time for"
    ]
    matched_rfq_keywords = [k for k in rfq_keywords if k in combined_text]
    if matched_rfq_keywords:
        return EmailClassificationResult(
            intent=EmailIntent.CUSTOMER_RFQ,
            event_type="erp.crm.inbound_rfq_email",
            is_commercial_actionable=True,
            confidence=0.92,
            detected_keywords=matched_rfq_keywords,
            summary_reason="Customer inquiry or Request for Quotation (RFQ) detected.",
        )

    # 5. Default Fallback
    return EmailClassificationResult(
        intent=EmailIntent.CUSTOMER_RFQ,
        event_type="erp.crm.inbound_rfq_email",
        is_commercial_actionable=True,
        confidence=0.60,
        detected_keywords=[],
        summary_reason="General commercial inquiry; routing to Revenue Agent evaluation.",
    )
