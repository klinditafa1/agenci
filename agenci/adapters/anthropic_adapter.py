"""Adapter for the Anthropic Messages API.

Implemented directly against the REST ``/v1/messages`` endpoint with
``httpx`` rather than the ``anthropic`` SDK, mirroring the ``openai``
adapter's approach — keeps the base dependency set small, and the
adapter works unmodified against any Anthropic-compatible ``base_url``
(e.g. a proxy or gateway that implements the same Messages API shape).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from agenci.adapters.base import AgentResponse

DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapterError(Exception):
    pass


class AnthropicAdapter:
    def __init__(
        self,
        model: str,
        api_key_env: str = "ANTHROPIC_API_KEY",
        base_url: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        anthropic_version: str = DEFAULT_ANTHROPIC_VERSION,
        timeout_seconds: float = 60.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise AnthropicAdapterError(
                f"Environment variable {api_key_env} is not set. "
                f"Set it or configure agent.api_key_env in agenci.yaml."
            )
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=base_url or DEFAULT_BASE_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": anthropic_version,
                "content-type": "application/json",
            },
            timeout=timeout_seconds,
        )

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": input}],
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt

        start = time.perf_counter()
        try:
            response = await self._client.post("/v1/messages", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            return AgentResponse(output="", error=f"Anthropic API error: {exc}")
        latency_ms = (time.perf_counter() - start) * 1000
        _ = latency_ms

        try:
            output = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            return AgentResponse(output="", error=f"Unexpected response shape from the Messages API: {exc}")

        usage = data.get("usage", {})
        return AgentResponse(
            output=output,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            model=data.get("model", self.model),
            provider="anthropic",
            raw=data,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
