"""Server-side SafePay hosted subscription checkout integration."""

import asyncio
import time
from urllib.parse import urlencode

import httpx

from erp.config import settings


class SafePayService:
    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    @property
    def api_host(self) -> str:
        return (settings.SAFEPAY_HOST or self._default_api_host()).rstrip("/")

    @property
    def checkout_host(self) -> str:
        return (settings.SAFEPAY_CHECKOUT_HOST or self._default_checkout_host()).rstrip("/")

    @staticmethod
    def _default_api_host() -> str:
        return (
            "https://api.getsafepay.com"
            if settings.SAFEPAY_ENV.lower() in {"production", "live"}
            else "https://sandbox.api.getsafepay.com"
        )

    @staticmethod
    def _default_checkout_host() -> str:
        return (
            "https://getsafepay.com"
            if settings.SAFEPAY_ENV.lower() in {"production", "live"}
            else "https://sandbox.api.getsafepay.com"
        )

    def is_configured(self) -> bool:
        return bool(settings.SAFEPAY_SECRET_KEY)

    async def _get_auth_token(self, *, force_refresh: bool = False) -> str:
        if not settings.SAFEPAY_SECRET_KEY:
            raise RuntimeError("SafePay server secret is not configured.")

        now = time.monotonic()
        if not force_refresh and self._token and now < self._token_expires_at - 300:
            return self._token

        async with self._token_lock:
            now = time.monotonic()
            if not force_refresh and self._token and now < self._token_expires_at - 300:
                return self._token
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.api_host}/client/passport/v1/token",
                    headers={"X-SFPY-MERCHANT-SECRET": settings.SAFEPAY_SECRET_KEY},
                    json={},
                )
                response.raise_for_status()
                response_body = response.json()
                token = response_body.get("data") if isinstance(response_body, dict) else None
                if not isinstance(token, str) or not token.strip():
                    raise RuntimeError("SafePay did not return an authentication token.")
                token = token.strip()
                self._token = token
                self._token_expires_at = now + 3600
                return token

    async def create_subscription_checkout(
        self, plan_id: str, reference: str, redirect_url: str, cancel_url: str
    ) -> str:
        # Start every checkout session with a fresh token. This avoids sending
        # SafePay a token rejected by a prior/expired checkout attempt.
        token = await self._get_auth_token(force_refresh=True)
        params = urlencode(
            {
                "plan_id": plan_id,
                "auth_token": token,
                "env": "production" if settings.SAFEPAY_ENV.lower() in {"production", "live"} else "sandbox",
                "reference": reference,
                "redirect_url": redirect_url,
                "cancel_url": cancel_url,
            }
        )
        return f"{self.checkout_host}/checkout/auth/login?{params}"

    async def cancel_subscription(self, subscription_id: str) -> None:
        if not settings.SAFEPAY_SECRET_KEY:
            raise RuntimeError("SafePay server secret is not configured.")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.api_host}/subscriptions/v1/{subscription_id}/cancel",
                headers={"X-SFPY-MERCHANT-SECRET": settings.SAFEPAY_SECRET_KEY},
                json={},
            )
            response.raise_for_status()


safepay_service = SafePayService()
