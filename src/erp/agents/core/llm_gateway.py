"""Provider-aware OpenAI-compatible gateway for structured agent reasoning."""

import asyncio
from contextvars import ContextVar
import json
import logging
import re
from typing import Any

import httpx

from erp.config import settings

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """The selected provider is missing valid configuration."""


class LLMProviderError(RuntimeError):
    """The configured model could not produce a usable response."""


class LLMGateway:
    """Calls Gemini directly or through OpenRouter using their OpenAI-compatible APIs."""

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER.strip().lower()
        if self.provider == "openrouter":
            self.api_key = settings.OPENROUTER_API_KEY
            self.base_url = settings.OPENROUTER_BASE_URL
            self.model_name = settings.LLM_MODEL or "google/gemini-3.8-flash"
        elif self.provider == "gemini":
            self.api_key = settings.GEMINI_API_KEY
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            self.model_name = settings.LLM_MODEL or settings.GEMINI_MODEL
        else:
            raise LLMConfigurationError("LLM_PROVIDER must be 'openrouter' or 'gemini'.")

        self.base_url = self.base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"
        self._usage: ContextVar[dict[str, Any] | None] = ContextVar(
            f"llm_usage_{id(self)}", default=None
        )

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMConfigurationError(f"API credentials are not configured for provider '{self.provider}'.")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    @property
    def last_usage(self) -> dict[str, Any] | None:
        """Aggregated measured usage for the current async execution context."""
        return self._usage.get()

    def reset_usage(self) -> None:
        """Begin collecting provider usage for one agent execution context."""
        self._usage.set({"llm_calls": 0, "usage_available": True})

    def usage_snapshot(self) -> dict[str, Any] | None:
        usage = self._usage.get()
        return dict(usage) if usage else None

    async def ainvoke_text(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Invoke the configured provider with bounded retries for transient failures."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = self._headers()

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(self.endpoint, headers=headers, json=payload)
                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < self.MAX_ATTEMPTS:
                        await asyncio.sleep(0.4 * (2 ** (attempt - 1)))
                        continue
                    raise LLMProviderError(
                        f"Provider '{self.provider}' returned retryable HTTP {response.status_code} after retries."
                    )
                if not response.is_success:
                    raise LLMProviderError(
                        f"Provider '{self.provider}' returned HTTP {response.status_code}."
                    )

                result = response.json()
                if not isinstance(result, dict):
                    raise LLMProviderError("LLM provider returned an invalid response envelope.")
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise LLMProviderError("LLM response did not contain a completion choice.")
                message = choices[0].get("message", {})
                if not isinstance(message, dict):
                    raise LLMProviderError("LLM completion choice had an invalid message.")
                content = message.get("content")
                if isinstance(content, list):
                    content = "".join(
                        block.get("text", "") for block in content if isinstance(block, dict)
                    )
                if not isinstance(content, str) or not content.strip():
                    raise LLMProviderError("LLM response contained no text content.")
                usage = result.get("usage")
                snapshot = dict(self._usage.get() or {"llm_calls": 0, "usage_available": True})
                snapshot["llm_calls"] += 1
                if isinstance(usage, dict):
                    aliases = {
                        "prompt_tokens": ("prompt_tokens", "input_tokens"),
                        "completion_tokens": ("completion_tokens", "output_tokens"),
                        "total_tokens": ("total_tokens",),
                    }
                    for metric, keys in aliases.items():
                        for key in keys:
                            value = usage.get(key)
                            if isinstance(value, (int, float)) and value >= 0:
                                snapshot[metric] = snapshot.get(metric, 0) + int(value)
                                break
                    if isinstance(usage.get("cost"), (int, float)) and usage["cost"] >= 0:
                        snapshot["provider_reported_cost"] = snapshot.get("provider_reported_cost", 0.0) + float(usage["cost"])
                else:
                    snapshot["usage_available"] = False
                self._usage.set(snapshot)
                return content.strip()
            except LLMProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self.MAX_ATTEMPTS:
                    await asyncio.sleep(0.4 * (2 ** (attempt - 1)))
                    continue
                logger.warning("LLM provider request failed after retries (%s).", type(exc).__name__)
                raise LLMProviderError("LLM provider request failed after retries.") from exc
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("LLM provider returned an invalid response envelope.")
                raise LLMProviderError("LLM provider returned an invalid response.") from exc

        raise LLMProviderError("LLM provider request failed.")

    async def ainvoke_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Invoke the model and require a JSON object, without exposing raw output in errors."""
        json_system = (
            f"{system_prompt}\n\n" if system_prompt else ""
        ) + "Return only one valid JSON object. Do not include markdown or explanatory text."
        content = await self.ainvoke_text(prompt, system_prompt=json_system, temperature=temperature)
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            try:
                parsed = json.loads(match.group(1)) if match else None
            except json.JSONDecodeError as exc:
                raise LLMProviderError("LLM response was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("LLM response must be a JSON object.")
        return parsed


llm_gateway = LLMGateway()
