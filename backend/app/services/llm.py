"""LLM provider abstraction with structured JSON output."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when a live LLM request fails. Never silently substituted."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMProvider:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    @property
    def model_name(self) -> str:
        return self.settings.llm_model if self.configured else "none"

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[T],
        temperature: float = 0.3,
    ) -> tuple[T, str]:
        """Return validated model instance and model name used.

        Raises LLMError when not configured or when the provider fails.
        Does not fabricate output.
        """
        if not self.configured:
            raise LLMError(
                "LLM is not configured. Set LLM_API_KEY and LLM_PROVIDER for live mode, "
                "or use demo mode / deterministic analysis fallbacks where documented.",
                retryable=False,
            )

        payload = {
            "model": self.settings.llm_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

        # Dating runs make thousands of calls; ride out rate limits and blips.
        attempts = self.settings.llm_max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                data = await self._post(url, headers, payload)
                break
            except LLMError as exc:
                if not exc.retryable or attempt == attempts:
                    raise
                await asyncio.sleep(1.5 * attempt)

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected LLM response shape", retryable=False) from exc

        try:
            parsed = json.loads(_strip_fences(content))
        except (json.JSONDecodeError, TypeError) as exc:
            raise LLMError("LLM returned non-JSON content", retryable=False) from exc

        try:
            validated = schema_model.model_validate(parsed)
        except ValidationError as exc:
            raise LLMError(f"LLM JSON failed schema validation: {exc}", retryable=False) from exc

        return validated, self.settings.llm_model

    async def _post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM request timed out: {exc}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM transport error: {exc}", retryable=True) from exc

        if response.status_code == 429:
            raise LLMError("LLM rate limited", retryable=True)
        if response.status_code >= 500:
            raise LLMError(f"LLM server error {response.status_code}", retryable=True)
        if response.status_code >= 400:
            # Do not log API key or full body with secrets
            raise LLMError(
                f"LLM request rejected ({response.status_code})",
                retryable=False,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LLMError("LLM returned a non-JSON response body", retryable=True) from exc


def _strip_fences(content: Any) -> str:
    """Unwrap ```json fences that some OpenAI-compatible models add around JSON."""
    text = str(content or "").strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    return match.group(1) if match else text
