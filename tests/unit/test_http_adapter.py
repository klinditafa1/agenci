from __future__ import annotations

import httpx
import pytest
import respx

from agenci.adapters.http_adapter import HttpAdapter


@pytest.mark.asyncio
@respx.mock
async def test_http_adapter_success() -> None:
    route = respx.post("http://agent.local/run").mock(
        return_value=httpx.Response(
            200,
            json={"output": "hello from remote agent", "input_tokens": 10, "output_tokens": 5},
        )
    )
    adapter = HttpAdapter("http://agent.local/run")
    try:
        response = await adapter.run("hi", {"user": "klindi"})
        assert route.called
        assert response.output == "hello from remote agent"
        assert response.input_tokens == 10
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_http_adapter_missing_output_field() -> None:
    respx.post("http://agent.local/run").mock(return_value=httpx.Response(200, json={"foo": 1}))
    adapter = HttpAdapter("http://agent.local/run")
    try:
        response = await adapter.run("hi", {})
        assert response.error is not None
        assert "output" in response.error
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_http_adapter_error_status() -> None:
    respx.post("http://agent.local/run").mock(return_value=httpx.Response(500, text="boom"))
    adapter = HttpAdapter("http://agent.local/run")
    try:
        response = await adapter.run("hi", {})
        assert response.error is not None
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_http_adapter_reports_tool_calls() -> None:
    respx.post("http://agent.local/run").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": "done",
                "tool_calls": [{"tool": "search", "arguments": {"q": "x"}}],
            },
        )
    )
    adapter = HttpAdapter("http://agent.local/run")
    try:
        response = await adapter.run("hi", {})
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool == "search"
    finally:
        await adapter.aclose()
