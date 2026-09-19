"""Optional LLM wiring for the business agents (DashScope-compatible).

Selection (``TRAVEL_LLM_BACKEND``):

- ``auto`` (default): enable the remote LLM when an API key is configured
  (``AI_DASHSCOPE_API_KEY`` / ``DASHSCOPE_API_KEY`` / ``TRAVEL_LLM_API_KEY``),
  otherwise return :class:`NullLlmProvider` so agents keep the deterministic
  template reasons.
- ``off``: force-disable (tests, air-gapped environments).
- ``dashscope``: force-enable; hard failure when the key is missing.

The DashScope OpenAI-compatible endpoint is used so the same client also works
for self-hosted OpenAI-protocol servers (vLLM etc.) via ``TRAVEL_LLM_BASE_URL``.
Every remote failure degrades to the template rationale — the recommendation
pipeline never breaks because the LLM is down.
"""

from __future__ import annotations

import logging
import os
from typing import List, Protocol

logger = logging.getLogger("travel_agent.agents.llm")

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DASHSCOPE_CHAT_MODEL = "qwen-plus"
DEFAULT_TIMEOUT_SEC = 8.0
MAX_ITEMS_FOR_PROMPT = 8


class RationaleProvider(Protocol):
    """Produces short reasons for engagement recommendation items."""

    provider_name: str

    def refine_reasons(self, request_context: dict, items: List[dict]) -> List[str]: ...


class NullLlmProvider:
    """No-op provider: agents keep their deterministic template reasons."""

    provider_name = "null"

    def refine_reasons(self, request_context: dict, items: List[dict]) -> List[str]:
        return [str(item.get("reason", "")) for item in items]


class DashScopeLlmProvider:
    """DashScope OpenAI-compatible chat completions (qwen family by default)."""

    def __init__(self) -> None:
        self._api_key = (
            os.getenv("TRAVEL_LLM_API_KEY", "")
            or os.getenv("AI_DASHSCOPE_API_KEY", "")
            or os.getenv("DASHSCOPE_API_KEY", "")
        ).strip()
        self._base_url = os.getenv("TRAVEL_LLM_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL).rstrip("/")
        self._model = os.getenv("TRAVEL_LLM_MODEL", DEFAULT_DASHSCOPE_CHAT_MODEL)
        self._timeout = float(os.getenv("TRAVEL_LLM_TIMEOUT_SEC", str(DEFAULT_TIMEOUT_SEC)))
        self.provider_name = f"dashscope:{self._model}"

    def refine_reasons(self, request_context: dict, items: List[dict]) -> List[str]:
        titles = [str(item.get("title", "")) for item in items[:MAX_ITEMS_FOR_PROMPT]]
        prompt = (
            "你是企业差旅推荐助手。针对以下推荐条目，各给一句不超过30字的中文理由，"
            "结合城市、偏好与预算。按行输出，每行一条，不要编号。\n"
            f"城市={request_context.get('city', '')}，"
            f"偏好={request_context.get('preferences', '')}，"
            f"预算={request_context.get('budget', '')}，天数={request_context.get('days', '')}\n"
            "条目：\n" + "\n".join(f"- {t}" for t in titles)
        )
        import requests

        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 512,
            },
            timeout=self._timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(f"llm chat failed: {status_code_text(response)}")
        content = (response.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        lines = [line.strip().lstrip("-• ").strip() for line in str(content).splitlines() if line.strip()]
        lines = [line for line in lines if line]
        if len(lines) < len(titles):
            raise RuntimeError(
                f"llm returned {len(lines)} reasons for {len(titles)} items"
            )
        return lines[: len(items)] + [str(item.get("reason", "")) for item in items[len(lines):]]


def status_code_text(response) -> str:
    return f"{response.status_code} {response.text[:200]}"


def create_rationale_provider() -> RationaleProvider:
    backend = os.getenv("TRAVEL_LLM_BACKEND", "auto").strip().lower()
    if backend in {"", "off", "none"}:
        return NullLlmProvider()

    def api_key() -> str:
        return (
            os.getenv("TRAVEL_LLM_API_KEY", "")
            or os.getenv("AI_DASHSCOPE_API_KEY", "")
            or os.getenv("DASHSCOPE_API_KEY", "")
        ).strip()

    if backend == "dashscope":
        if not api_key():
            logger.warning("TRAVEL_LLM_BACKEND=dashscope but no API key; using template reasons")
            return NullLlmProvider()
        return DashScopeLlmProvider()

    # auto and any future backend names: enable when a key exists.
    if api_key():
        return DashScopeLlmProvider()
    return NullLlmProvider()


class LlmRationaleDecorator:
    """Applies :class:`DashScopeLlmProvider` reasons to engagement items with
    graceful degradation: any provider error keeps the template reasons."""

    def __init__(self, provider: RationaleProvider) -> None:
        self.provider = provider

    def enrich(
        self, request_context: dict, items: List[dict]
    ) -> List[dict]:
        if not items:
            return items
        try:
            reasons = self.provider.refine_reasons(request_context, items)
            if len(reasons) < len(items):
                raise RuntimeError("provider returned fewer reasons than items")
        except Exception as exc:
            logger.warning(
                "LLM rationale unavailable (%s); keeping template reasons",
                exc,
            )
            return items
        enriched: List[dict] = []
        for item, reason in zip(items, reasons):
            row = dict(item)
            if reason:
                row["reason"] = reason
            row["reasonSource"] = self.provider.provider_name
            enriched.append(row)
        return enriched
