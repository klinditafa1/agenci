from __future__ import annotations

import pytest

pytest.importorskip("autogen_agentchat")

from agenci.adapters.autogen_adapter import AutoGenAdapter, AutoGenAdapterError  # noqa: E402


@pytest.mark.asyncio
async def test_autogen_adapter_runs_and_captures_real_tool_call() -> None:
    adapter = AutoGenAdapter("sample_agent:build_autogen_agent")
    response = await adapter.run("What's the status of order 1001?", {})
    assert response.output == "shipped"
    assert response.error is None
    assert response.provider == "autogen"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "lookup_order"
    assert response.tool_calls[0].arguments == {"order_id": "1001"}
    assert response.tool_calls[0].result == "shipped"


@pytest.mark.asyncio
async def test_autogen_adapter_reports_token_usage() -> None:
    adapter = AutoGenAdapter("sample_agent:build_autogen_agent")
    response = await adapter.run("What's the status of order 1001?", {})
    assert response.input_tokens == 50
    assert response.output_tokens == 10


@pytest.mark.asyncio
async def test_autogen_adapter_resets_state_between_calls() -> None:
    """The factory builds one agent instance reused across test cases;
    the adapter must reset it so run 2 doesn't see run 1's conversation."""
    adapter = AutoGenAdapter("sample_agent:build_autogen_agent")
    r1 = await adapter.run("first question", {})
    r2 = await adapter.run("second question", {})

    assert r1.output == "shipped"
    assert r2.output == "shipped"  # second canned response, not a leftover from run 1
    # The first message of run 2's transcript is run 2's own input, not run 1's.
    assert r2.raw.messages[0].content == "second question"
    assert len(r2.raw.messages) == len(r1.raw.messages)


@pytest.mark.asyncio
async def test_autogen_adapter_error_does_not_raise() -> None:
    adapter = AutoGenAdapter("sample_agent:build_broken_autogen_agent")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "agent exploded" in response.error


@pytest.mark.asyncio
async def test_autogen_adapter_rejects_non_runner_entrypoint() -> None:
    adapter = AutoGenAdapter("sample_agent:not_an_autogen_agent")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "did not resolve to an AutoGen agent or team" in response.error


def test_invalid_entrypoint_format() -> None:
    with pytest.raises(AutoGenAdapterError):
        AutoGenAdapter("not_a_valid_entrypoint")


def test_missing_module() -> None:
    with pytest.raises(AutoGenAdapterError):
        AutoGenAdapter("nonexistent_module_xyz:fn")
