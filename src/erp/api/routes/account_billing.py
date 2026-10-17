"""Tenant-facing SaaS subscription and SafePay checkout API."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from erp.api.deps import CurrentUserDep, DbSessionDep
from erp.config import settings
from erp.db.models.saas_subscription import SaaSSubscription
from erp.db.models.tenant import Tenant
from erp.workflows.billing.safepay_service import safepay_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing/account-subscription", tags=["SaaS Subscription"])


class CreateCheckoutRequest(BaseModel):
    plan_code: str = Field(pattern="^(monthly|annual)$")


def _plan_payload(plan_code: str, name: str, plan_id: str | None, amount: Decimal, interval: str) -> dict:
    return {
        "code": plan_code,
        "configured": bool(safepay_service.is_configured() and plan_id),
        "name": name,
        "amount": str(amount),
        "currency": settings.SAFEPAY_PLAN_CURRENCY.upper(),
        "interval": interval,
        "plan_id": plan_id,
        "environment": settings.SAFEPAY_ENV.lower(),
    }


def _plan_payloads() -> list[dict]:
    return [
        _plan_payload(
            "monthly", "Monthly", settings.SAFEPAY_MONTHLY_PLAN_ID,
            settings.SAFEPAY_MONTHLY_PLAN_PRICE, "MONTH",
        ),
        _plan_payload(
            "annual", "Annual", settings.SAFEPAY_ANNUAL_PLAN_ID,
            settings.SAFEPAY_ANNUAL_PLAN_PRICE, "YEAR",
        ),
    ]


def _subscription_payload(sub: SaaSSubscription | None) -> dict | None:
    if not sub:
        return None
    return {
        "id": str(sub.subscription_id),
        "plan_name": sub.plan_name,
        "status": sub.status,
        "currency": sub.currency,
        "amount": str(sub.amount) if sub.amount is not None else None,
        "billing_interval": sub.billing_interval,
        "reference": sub.reference,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "last_payment_at": sub.last_payment_at.isoformat() if sub.last_payment_at else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "cancellation_requested_at": (
            sub.cancellation_requested_at.isoformat() if sub.cancellation_requested_at else None
        ),
    }


def _subscription_has_access(sub: SaaSSubscription, now: datetime | None = None) -> bool:
    if sub.status == "active":
        return True
    now = now or datetime.now(UTC)
    return sub.status == "trialing" and bool(sub.current_period_end and sub.current_period_end > now)


@router.get("/plans")
async def get_subscription_plans(_: CurrentUserDep):
    """Returns the configured SafePay plan without exposing merchant credentials."""
    return _plan_payloads()


@router.get("/status")
async def get_subscription_status(user: CurrentUserDep, db: DbSessionDep):
    stmt = (
        select(SaaSSubscription)
        .where(SaaSSubscription.tenant_id == user.tenant_id)
        .order_by(SaaSSubscription.created_at.desc())
        .limit(20)
    )
    subscriptions = list((await db.execute(stmt)).scalars().all())
    current = next((sub for sub in subscriptions if _subscription_has_access(sub)), None)
    if current is None and subscriptions:
        current = subscriptions[0]
    subscription_required = settings.REQUIRE_ACTIVE_SAAS_SUBSCRIPTION
    return {
        "plans": _plan_payloads(),
        "subscription": _subscription_payload(current),
        "history": [_subscription_payload(sub) for sub in subscriptions],
        # The frontend guard consumes this endpoint too. Reflect the same
        # enforcement switch used by the API dependency so an explicitly
        # disabled subscription requirement does not leave users redirected.
        "has_access": (
            not subscription_required
            or any(_subscription_has_access(sub) for sub in subscriptions)
        ),
        "subscription_required": subscription_required,
    }


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_subscription_checkout(
    payload: CreateCheckoutRequest, user: CurrentUserDep, db: DbSessionDep
):
    """Creates and persists a pending checkout before returning its hosted URL."""
    if user.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Only tenant administrators can manage billing.")
    selected_plan = next((plan for plan in _plan_payloads() if plan["code"] == payload.plan_code), None)
    if not selected_plan or not selected_plan["configured"]:
        raise HTTPException(
            status_code=503,
            detail=f"The SafePay {payload.plan_code} plan is not configured.",
        )

    active = await db.scalar(
        select(SaaSSubscription.subscription_id).where(
            SaaSSubscription.tenant_id == user.tenant_id,
            or_(
                SaaSSubscription.status == "active",
                and_(
                    SaaSSubscription.status == "trialing",
                    SaaSSubscription.current_period_end > datetime.now(UTC),
                ),
            ),
        ).limit(1)
    )
    if active:
        raise HTTPException(status_code=409, detail="This workspace already has an active subscription.")

    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    now = datetime.now(UTC)
    pending = await db.scalar(
        select(SaaSSubscription)
        .where(
            SaaSSubscription.tenant_id == user.tenant_id,
            SaaSSubscription.status == "pending",
            SaaSSubscription.plan_id == selected_plan["plan_id"],
            SaaSSubscription.created_at >= now - timedelta(minutes=30),
        )
        .order_by(SaaSSubscription.created_at.desc())
        .limit(1)
    )
    if pending:
        subscription = pending
    else:
        subscription = SaaSSubscription(
            tenant_id=user.tenant_id,
            plan_id=selected_plan["plan_id"],
            plan_name=f"AI-Native ERP {selected_plan['name']}",
            reference=f"erp_{uuid.uuid4().hex}",
            status="pending",
            currency=settings.SAFEPAY_PLAN_CURRENCY.upper(),
            amount=Decimal(selected_plan["amount"]),
            billing_interval=selected_plan["interval"],
        )
        db.add(subscription)
        await db.flush()

    base_url = settings.FRONTEND_BASE_URL.rstrip("/")
    return_url = f"{base_url}/billing/subscription?payment=returned&reference={subscription.reference}"
    cancel_url = f"{base_url}/billing/subscription?payment=cancelled&reference={subscription.reference}"
    try:
        checkout_url = await safepay_service.create_subscription_checkout(
            selected_plan["plan_id"], subscription.reference, return_url, cancel_url
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.exception("SafePay checkout creation failed for tenant %s", user.tenant_id)
        raise HTTPException(status_code=502, detail="Could not start SafePay checkout. Please try again.") from exc

    return {"checkout_url": checkout_url, "reference": subscription.reference}


@router.post("/cancel")
async def cancel_subscription(user: CurrentUserDep, db: DbSessionDep):
    """Requests cancellation from SafePay; webhook state remains authoritative."""
    if user.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Only tenant administrators can manage billing.")
    subscription = await db.scalar(
        select(SaaSSubscription)
        .where(
            SaaSSubscription.tenant_id == user.tenant_id,
            or_(
                SaaSSubscription.status == "active",
                and_(
                    SaaSSubscription.status == "trialing",
                    SaaSSubscription.current_period_end > datetime.now(UTC),
                ),
            ),
        )
        .order_by(SaaSSubscription.created_at.desc())
        .limit(1)
    )
    if not subscription or not subscription.safepay_subscription_id:
        raise HTTPException(status_code=409, detail="There is no active SafePay subscription to cancel.")
    if subscription.cancellation_requested_at:
        return {"status": subscription.status, "cancellation_requested": True}

    try:
        await safepay_service.cancel_subscription(subscription.safepay_subscription_id)
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.exception("SafePay cancellation request failed for tenant %s", user.tenant_id)
        raise HTTPException(status_code=502, detail="SafePay could not process the cancellation request.") from exc
    subscription.cancellation_requested_at = datetime.now(UTC)
    await db.flush()
    return {"status": subscription.status, "cancellation_requested": True}
