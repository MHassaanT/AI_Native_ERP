"""Verified SafePay subscription webhook receiver."""

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import func, select

from erp.api.deps import DbSessionDep
from erp.config import settings
from erp.db.models.saas_subscription import SafePayWebhookEvent, SaaSSubscription
from erp.db.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/safepay", tags=["SafePay Webhooks"])


def _event_datetime(value: Any) -> datetime | None:
    if isinstance(value, dict) and isinstance(value.get("seconds"), (int, float)):
        return datetime.fromtimestamp(value["seconds"], tz=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _verified_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = settings.SAFEPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    received = signature.strip().lower()
    if received.startswith("sha256="):
        received = received[7:]
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.post("/subscriptions")
async def receive_subscription_webhook(
    request: Request,
    db: DbSessionDep,
    signature: str | None = Header(default=None, alias="X-SFPY-SIGNATURE"),
):
    raw_body = await request.body()
    if not settings.SAFEPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="SafePay webhook verification is not configured.")
    if not _verified_signature(raw_body, signature):
        logger.warning("Rejected SafePay webhook because its signature did not verify.")
        raise HTTPException(status_code=401, detail="Invalid SafePay webhook signature.")

    try:
        event = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload.") from exc
    if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
        raise HTTPException(status_code=400, detail="Malformed SafePay webhook payload.")

    event_id = event.get("id") or event.get("token")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(status_code=400, detail="SafePay webhook is missing event ID or type.")
    event_type = event_type.strip().lower()

    existing = await db.get(SafePayWebhookEvent, event_id)
    if existing and not existing.processing_error:
        return {"ok": True, "duplicate": True}
    if existing:
        # A prior delivery was persisted but could not be correlated. Reprocess
        # it on SafePay's retry instead of permanently swallowing the event.
        record = existing
        record.processing_error = None
    else:
        record = SafePayWebhookEvent(event_id=event_id, event_type=event_type, payload=event)
        db.add(record)

    logger.info("Received SafePay webhook event %s (%s).", event_type, event_id)
    data = event["data"]
    metadata = data.get("metadata")
    nested_subscription = data.get("subscription")
    reference = (
        data.get("reference")
        or (metadata.get("reference") if isinstance(metadata, dict) else None)
        or (nested_subscription.get("reference") if isinstance(nested_subscription, dict) else None)
    )
    safepay_id = data.get("subscription_id") or data.get("sub_id") or data.get("id")
    if isinstance(reference, str):
        subscription = await db.scalar(
            select(SaaSSubscription).where(SaaSSubscription.reference == reference).with_for_update()
        )
    elif isinstance(safepay_id, str):
        subscription = await db.scalar(
            select(SaaSSubscription)
            .where(SaaSSubscription.safepay_subscription_id == safepay_id)
            .with_for_update()
        )
    else:
        subscription = None

    # SafePay's documented v2 subscription payloads may omit the merchant
    # reference. For the first event, safely associate it by plan + billing
    # email only when there is exactly one recent candidate.
    plan_id = data.get("plan_id")
    customer_email = data.get("customer_email")
    if (
        subscription is None
        and isinstance(plan_id, str)
        and isinstance(customer_email, str)
    ):
        candidates = list((await db.execute(
            select(SaaSSubscription)
            .join(User, User.tenant_id == SaaSSubscription.tenant_id)
            .where(
                SaaSSubscription.plan_id == plan_id,
                SaaSSubscription.status == "pending",
                func.lower(User.email) == customer_email.strip().lower(),
                SaaSSubscription.created_at >= datetime.now(UTC) - timedelta(days=7),
            )
            .order_by(SaaSSubscription.created_at.desc())
            .limit(2)
            .with_for_update(of=SaaSSubscription)
        )).scalars().all())
        if len(candidates) == 1:
            subscription = candidates[0]
            logger.info("Matched SafePay subscription event by unique plan and billing email.")
        elif len(candidates) > 1:
            logger.error("SafePay event matched multiple subscriptions by plan and billing email.")

    if subscription:
        received_plan_id = data.get("plan_id")
        if received_plan_id and received_plan_id != subscription.plan_id:
            record.processing_error = "SafePay event plan ID did not match the stored checkout plan."
            logger.error("SafePay plan mismatch for reference %s", reference)
        else:
            if isinstance(safepay_id, str):
                subscription.safepay_subscription_id = safepay_id

            if event_type == "subscription.created":
                # A verified SafePay trial grants access only through the
                # provider-reported period end. Creation alone never implies paid.
                provider_status = str(data.get("status") or "").upper()
                subscription.current_period_start = _event_datetime(
                    data.get("current_period_start_date") or data.get("started_at")
                ) or subscription.current_period_start
                subscription.current_period_end = _event_datetime(
                    data.get("trial_end_date")
                    or data.get("trial_ends_at")
                    or data.get("current_period_end_date")
                ) or subscription.current_period_end
                if subscription.status not in {"active", "past_due", "cancelled", "ended"}:
                    if (
                        provider_status == "TRIALING"
                        and subscription.current_period_end
                        and subscription.current_period_end > datetime.now(UTC)
                    ):
                        subscription.status = "trialing"
                    else:
                        subscription.status = "pending"
            elif event_type == "subscription.payment.succeeded":
                subscription.status = "active"
                subscription.last_payment_at = _event_datetime(
                    data.get("last_paid_date") or data.get("paid_at") or event.get("created_at")
                ) or datetime.now(UTC)
                subscription.current_period_start = _event_datetime(
                    data.get("current_period_start_date")
                ) or subscription.current_period_start
                subscription.current_period_end = _event_datetime(
                    data.get("current_period_end_date")
                ) or subscription.current_period_end
            elif event_type == "subscription.payment.failed":
                subscription.status = "past_due"
            elif event_type in {"subscription.cancelled", "subscription.canceled"}:
                subscription.status = "cancelled"
                subscription.cancelled_at = _event_datetime(
                    data.get("cancelled_at") or data.get("canceled_at") or event.get("created_at")
                ) or datetime.now(UTC)
            elif event_type == "subscription.ended":
                subscription.status = "ended"
            elif event_type == "subscription.paused":
                subscription.status = "paused"
            elif event_type == "subscription.resumed":
                subscription.status = "active"
    elif event_type.startswith("subscription."):
        record.processing_error = "No pending subscription matched the SafePay reference."
        logger.warning("Unmatched SafePay subscription webhook reference: %s", reference)

    record.processed_at = datetime.now(UTC)
    await db.commit()
    if record.processing_error == "No pending subscription matched the SafePay reference.":
        # Ask SafePay to retry. The event remains available for audit and is
        # eligible for reprocessing when its subscription correlation appears.
        raise HTTPException(status_code=503, detail="Subscription reference is not available yet.")
    return {"ok": True, "duplicate": False}
