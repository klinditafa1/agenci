"""Adapter for OpenAI-compatible chat completion APIs.

Implemented directly against the REST ``/chat/completions`` endpoint
with ``httpx`` rather than the ``openai`` SDK, so the base dependency
set stays small and the adapter works unmodified against any
OpenAI-compatible endpoint (self-hosted vLLM/Ollama gateways, Azure
OpenAI-compatible routes, OpenRouter, etc.) by pointing ``base_url``
elsewhere.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from agenci.adapters.base import AgentResponse

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIAdapterError(Exception):
    pass


class OpenAIAdapter:
    def __init__(
        self,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        system_prompt: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise OpenAIAdapterError(
                f"Environment variable {api_key_env} is not set. "
                f"Set it or configure agent.api_key_env in agenci.yaml."
            )
        self.model = model
        self.system_prompt = system_prompt
        self._client = httpx.AsyncClient(
            base_url=base_url or DEFAULT_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": input})

        start = time.perf_counter()
        try:
            response = await self._client.post(
                "/chat/completions",
                json={"model": self.model, "messages": messages},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            return AgentResponse(output="", error=f"OpenAI-compatible API error: {exc}")
        latency_ms = (time.perf_counter() - start) * 1000
        _ = latency_ms

        try:
            output = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            return AgentResponse(
                output="", error=f"Unexpected response shape from chat completions API: {exc}"
            )

        usage = data.get("usage", {})
        return AgentResponse(
            output=output,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            model=data.get("model", self.model),
            provider="openai-compatible",
            raw=data,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
