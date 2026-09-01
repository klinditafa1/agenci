from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")

from agenci.adapters.langchain_adapter import LangChainAdapter, LangChainAdapterError  # noqa: E402


@pytest.mark.asyncio
async def test_langchain_chain_runs_and_returns_output() -> None:
    adapter = LangChainAdapter("sample_agent:build_langchain_chain")
    response = await adapter.run("hello there", {})
    assert response.output == "lc-ack: hello there"
    assert response.error is None
    assert response.provider == "langchain"


@pytest.mark.asyncio
async def test_langchain_adapter_captures_real_tool_call() -> None:
    adapter = LangChainAdapter("sample_agent:build_langchain_chain_with_tool")
    response = await adapter.run("one two three four", {})
    assert response.output == "4 words"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "word_count"
    assert response.tool_calls[0].result == "4"


@pytest.mark.asyncio
async def test_langchain_adapter_error_does_not_raise() -> None:
    adapter = LangChainAdapter("sample_agent:broken_langchain_chain")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "chain exploded" in response.error


def test_invalid_entrypoint_format() -> None:
    with pytest.raises(LangChainAdapterError):
        LangChainAdapter("not_a_valid_entrypoint")


def test_non_runnable_entrypoint_raises() -> None:
    with pytest.raises(LangChainAdapterError):
        LangChainAdapter("sample_agent:run_agent")  # a plain function, not a Runnable
