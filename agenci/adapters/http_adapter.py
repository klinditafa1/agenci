"""Adapter for agents exposed over HTTP/REST.

Agenci POSTs ``{"input": ..., "context": ...}`` to the configured URL
and expects a JSON body shaped like::

    {
      "output": "...",
      "tool_calls": [{"tool": "search", "arguments": {...}, "result": ...}],
      "input_tokens": 123,
      "output_tokens": 45,
      "model": "...",
      "provider": "..."
    }

Only ``output`` is required; every other field is optional and used to
enrich traces, cost tracking, and security checks when present.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from agenci.adapters.base import AgentResponse, ToolCallRecord


class HttpAdapter:
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.url = url
        self._client = httpx.AsyncClient(headers=headers or {}, timeout=timeout_seconds)

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        payload = {"input": input, "context": context or {}}
        start = time.perf_counter()
        try:
            response = await self._client.post(self.url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            return AgentResponse(output="", error=f"HTTP error calling {self.url}: {exc}")
        except ValueError as exc:
            return AgentResponse(output="", error=f"Agent at {self.url} did not return JSON: {exc}")
        _ = (time.perf_counter() - start) * 1000  # latency also measured by the caller

        if not isinstance(data, dict) or "output" not in data:
            return AgentResponse(
                output="",
                error=(f"Agent at {self.url} response is missing required 'output' field. Got: {data!r}"),
            )

        tool_calls = [ToolCallRecord(**tc) for tc in data.get("tool_calls", [])]
        return AgentResponse(
            output=str(data.get("output", "")),
            tool_calls=tool_calls,
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            model=data.get("model"),
            provider=data.get("provider"),
            raw=data,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
