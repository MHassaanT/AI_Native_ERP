"""LLM Gateway for AI-Native ERP Autonomous Workforce.

Provides a unified, production-ready interface to Google Gemini with JSON schema enforcement.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv

# Locate rebuild/.env robustly
_current_dir = os.path.dirname(os.path.abspath(__file__))
_rebuild_env = os.path.abspath(os.path.join(_current_dir, "..", "..", "..", "..", ".env"))
if os.path.exists(_rebuild_env):
    load_dotenv(_rebuild_env)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMGateway:
    """Manages LLM instances and structured generation."""

    def __init__(self):
        self.model_name = os.getenv("GEMINI_MODEL", "google/gemini-3.8-flash")
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self._llm = None

    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 2048):
        """Returns initialized LangChain Chat model targeting Gemini."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=45.0,
            default_headers={
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "AI-Native ERP Autonomous Workforce",
            },
        )

    async def ainvoke_text(self, prompt: str, system_prompt: str = "", temperature: float = 0.1) -> str:
        """Asynchronously invokes the LLM and returns text response."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        llm = self.get_chat_model(temperature=temperature)
        try:
            response = await llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM ainvoke_text failed: {e}")
            raise

    async def ainvoke_json(self, prompt: str, system_prompt: str = "", temperature: float = 0.1) -> Dict[str, Any]:
        """Asynchronously invokes the LLM and parses response as JSON dictionary."""
        prefix = f"{system_prompt}\n\n" if system_prompt else ""
        json_system = (
            prefix
            + "CRITICAL: You must return ONLY a valid, parseable JSON object. "
            "Do NOT include conversational preambles, introductory commentary, or postscript explanations. "
            "Wrap output in standard valid JSON format."
        )

        content = await self.ainvoke_text(prompt, system_prompt=json_system, temperature=temperature)

        # Strip markdown fences if present
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback regex extraction of outer JSON braces
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            logger.error(f"Failed to parse JSON from LLM response: {cleaned}")
            raise ValueError(f"LLM did not return valid JSON: {cleaned[:200]}")


llm_gateway = LLMGateway()
