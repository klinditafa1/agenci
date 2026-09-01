from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest.importorskip("mcp")

from agenci.adapters.mcp_adapter import (  # noqa: E402
    MCPAdapter,
    MCPAdapterError,
    _build_tool_arguments,
    _extract_text,
)


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResult:
    def __init__(self, text: str, is_error: bool = False) -> None:
        self.content = [_FakeContent(text)]
        self.isError = is_error


def test_build_tool_arguments_plain_text() -> None:
    assert _build_tool_arguments("hello world", None) == {"input": "hello world"}


def test_build_tool_arguments_json_object() -> None:
    assert _build_tool_arguments('{"a": 1, "b": 2}', None) == {"a": 1, "b": 2}


def test_build_tool_arguments_json_array_falls_back_to_input_key() -> None:
    # A JSON array isn't a mapping, so it's treated as plain text.
    assert _build_tool_arguments("[1, 2, 3]", None) == {"input": "[1, 2, 3]"}


def test_build_tool_arguments_context_override() -> None:
    result = _build_tool_arguments("ignored", {"mcp_arguments": {"x": 9}})
    assert result == {"x": 9}


def test_extract_text_joins_content_parts() -> None:
    result = _FakeResult("hello")
    assert _extract_text(result) == "hello"


@pytest.mark.asyncio
async def test_mcp_adapter_calls_tool_with_parsed_arguments() -> None:
    adapter = MCPAdapter(command="python3", tool="add")
    fake_session = AsyncMock()
    fake_session.call_tool.return_value = _FakeResult("42")
    adapter._session = fake_session  # bypass the real stdio handshake

    response = await adapter.run('{"a": 40, "b": 2}', {})

    fake_session.call_tool.assert_awaited_once_with("add", {"a": 40, "b": 2})
    assert response.output == "42"
    assert response.error is None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "add"
    assert response.provider == "mcp"


@pytest.mark.asyncio
async def test_mcp_adapter_reports_tool_error() -> None:
    adapter = MCPAdapter(command="python3", tool="risky_tool")
    fake_session = AsyncMock()
    fake_session.call_tool.return_value = _FakeResult("boom", is_error=True)
    adapter._session = fake_session

    response = await adapter.run("do something risky", {})

    assert response.error == "boom"
    assert response.tool_calls[0].error == "boom"


@pytest.mark.asyncio
async def test_mcp_adapter_connection_failure_returns_error_not_raise() -> None:
    adapter = MCPAdapter(command="nonexistent-binary-xyz", tool="add")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "Could not start/connect" in response.error


def test_missing_mcp_package_raises_clear_error(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mcp":
            raise ImportError("no module named mcp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(MCPAdapterError):
        MCPAdapter(command="python3", tool="add")
