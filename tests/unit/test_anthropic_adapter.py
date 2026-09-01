from __future__ import annotations

import httpx
import pytest
import respx

from agenci.adapters.anthropic_adapter import AnthropicAdapter, AnthropicAdapterError


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_success(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Hello there!"}],
                "usage": {"input_tokens": 12, "output_tokens": 5},
                "model": "claude-sonnet-5",
            },
        )
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5")
    try:
        response = await adapter.run("hi", {})
        assert route.called
        assert response.output == "Hello there!"
        assert response.input_tokens == 12
        assert response.output_tokens == 5
        assert response.provider == "anthropic"
        assert response.model == "claude-sonnet-5"
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_joins_multiple_text_blocks(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "Part one. "},
                    {"type": "text", "text": "Part two."},
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5")
    try:
        response = await adapter.run("hi", {})
        assert response.output == "Part one. Part two."
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_sends_system_prompt_and_max_tokens(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}], "usage": {}})
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5", system_prompt="Be terse.", max_tokens=64)
    try:
        await adapter.run("hi", {})
        import json

        payload = json.loads(route.calls.last.request.content)
        assert payload["system"] == "Be terse."
        assert payload["max_tokens"] == 64
        assert payload["model"] == "claude-sonnet-5"
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_http_error(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(529, json={"error": {"message": "overloaded"}})
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5")
    try:
        response = await adapter.run("hi", {})
        assert response.error is not None
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_unexpected_response_shape(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5")
    try:
        response = await adapter.run("hi", {})
        assert response.error is not None
    finally:
        await adapter.aclose()


def test_missing_api_key_raises_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AnthropicAdapterError):
        AnthropicAdapter(model="claude-sonnet-5")


@pytest.mark.asyncio
@respx.mock
async def test_custom_base_url_is_respected(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    route = respx.post("https://gateway.internal/v1/messages").mock(
        return_value=httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}], "usage": {}})
    )
    adapter = AnthropicAdapter(model="claude-sonnet-5", base_url="https://gateway.internal")
    try:
        await adapter.run("hi", {})
        assert route.called
    finally:
        await adapter.aclose()
