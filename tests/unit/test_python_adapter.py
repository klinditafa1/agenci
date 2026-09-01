from __future__ import annotations

import pytest

from agenci.adapters.python_adapter import PythonAdapter, PythonAdapterError


@pytest.mark.asyncio
async def test_sync_function_adapter() -> None:
    adapter = PythonAdapter("sample_agent:run_agent")
    response = await adapter.run("Please cancel my plan", {})
    assert "cancelled" in response.output
    assert response.error is None


@pytest.mark.asyncio
async def test_dict_response_with_tool_calls() -> None:
    adapter = PythonAdapter("sample_agent:agent_with_tools")
    response = await adapter.run("please delete everything", {})
    assert response.output
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "shell"


@pytest.mark.asyncio
async def test_async_function_adapter() -> None:
    adapter = PythonAdapter("sample_agent:async_agent")
    response = await adapter.run("hi", {})
    assert response.output == "async ack: hi"


@pytest.mark.asyncio
async def test_factory_adapter() -> None:
    adapter = PythonAdapter("sample_agent:create_agent")
    response = await adapter.run("hi", {})
    assert response.output == "factory ack: hi"


@pytest.mark.asyncio
async def test_broken_agent_returns_error_not_raise() -> None:
    adapter = PythonAdapter("sample_agent:broken_agent")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "boom" in response.error


def test_invalid_entrypoint_format() -> None:
    with pytest.raises(PythonAdapterError):
        PythonAdapter("not_a_valid_entrypoint")


def test_missing_module() -> None:
    with pytest.raises(PythonAdapterError):
        PythonAdapter("nonexistent_module_xyz:fn")
