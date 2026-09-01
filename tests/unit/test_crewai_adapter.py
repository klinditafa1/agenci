from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

pytest.importorskip("crewai")

from agenci.adapters.crewai_adapter import CrewAIAdapter, CrewAIAdapterError  # noqa: E402


def _install_fake_module(name: str, **attrs) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


class _FakeUsage:
    prompt_tokens = 100
    completion_tokens = 40


class _FakeOutput:
    raw = "The crew completed the task."
    token_usage = _FakeUsage()


class _FakeCrew:
    def __init__(
        self, should_error: bool = False, tool_calls: list[tuple[str, dict, str]] | None = None
    ) -> None:
        self.should_error = should_error
        self.received_inputs: dict | None = None
        self.tool_calls = tool_calls or []

    async def akickoff(self, inputs: dict) -> _FakeOutput:
        self.received_inputs = inputs
        if self.should_error:
            raise RuntimeError("crew failed")

        if self.tool_calls:
            import datetime

            from crewai.events import crewai_event_bus
            from crewai.events.types.tool_usage_events import (
                ToolUsageFinishedEvent,
                ToolUsageStartedEvent,
            )

            for tool_name, args, output in self.tool_calls:
                crewai_event_bus.emit(None, ToolUsageStartedEvent(tool_name=tool_name, tool_args=args))
                crewai_event_bus.emit(
                    None,
                    ToolUsageFinishedEvent(
                        tool_name=tool_name,
                        tool_args=args,
                        started_at=datetime.datetime.now(),
                        finished_at=datetime.datetime.now(),
                        output=output,
                    ),
                )
        return _FakeOutput()


@pytest.mark.asyncio
async def test_crewai_adapter_calls_factory_and_normalizes_output() -> None:
    _install_fake_module("fake_crewai_project", build_crew=lambda: _FakeCrew())
    adapter = CrewAIAdapter("fake_crewai_project:build_crew")
    response = await adapter.run("Plan a product launch", {})
    assert response.output == "The crew completed the task."
    assert response.input_tokens == 100
    assert response.output_tokens == 40
    assert response.provider == "crewai"
    assert response.error is None


@pytest.mark.asyncio
async def test_crewai_adapter_passes_input_under_configured_key() -> None:
    crew = _FakeCrew()
    _install_fake_module("fake_crewai_project2", build_crew=lambda: crew)
    adapter = CrewAIAdapter("fake_crewai_project2:build_crew", input_key="task")
    await adapter.run("Plan a product launch", {"priority": "high"})
    assert crew.received_inputs == {"task": "Plan a product launch", "priority": "high"}


@pytest.mark.asyncio
async def test_crewai_adapter_error_does_not_raise() -> None:
    _install_fake_module("fake_crewai_project3", build_crew=lambda: _FakeCrew(should_error=True))
    adapter = CrewAIAdapter("fake_crewai_project3:build_crew")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "crew failed" in response.error


@pytest.mark.asyncio
async def test_crewai_adapter_rejects_non_crew_entrypoint() -> None:
    _install_fake_module("fake_crewai_project4", build_crew=lambda: SimpleNamespace(nothing=True))
    adapter = CrewAIAdapter("fake_crewai_project4:build_crew")
    response = await adapter.run("hi", {})
    assert response.error is not None
    assert "did not resolve to a CrewAI Crew" in response.error


def test_invalid_entrypoint_format() -> None:
    with pytest.raises(CrewAIAdapterError):
        CrewAIAdapter("not_a_valid_entrypoint")


@pytest.mark.asyncio
async def test_crewai_adapter_captures_real_tool_call_via_event_bus() -> None:
    crew = _FakeCrew(tool_calls=[("lookup_order", {"order_id": "1001"}, "shipped")])
    _install_fake_module("fake_crewai_project5", build_crew=lambda: crew)
    adapter = CrewAIAdapter("fake_crewai_project5:build_crew")
    response = await adapter.run("What's the status of order 1001?", {})
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "lookup_order"
    assert response.tool_calls[0].arguments == {"order_id": "1001"}
    assert response.tool_calls[0].result == "shipped"


@pytest.mark.asyncio
async def test_crewai_adapter_isolates_tool_calls_between_runs() -> None:
    """Each .run() must only see its own tool calls — no cross-run leakage
    from the event bus's background thread-pool dispatch (see flush() usage
    in the adapter)."""
    call_count = {"n": 0}

    def factory():
        call_count["n"] += 1
        order_id = "1001" if call_count["n"] == 1 else "9999"
        return _FakeCrew(tool_calls=[("lookup_order", {"order_id": order_id}, order_id)])

    _install_fake_module("fake_crewai_project6", build_crew=factory)
    adapter = CrewAIAdapter("fake_crewai_project6:build_crew")

    response1 = await adapter.run("order 1001?", {})
    response2 = await adapter.run("order 9999?", {})

    assert response1.tool_calls[0].arguments == {"order_id": "1001"}
    assert response2.tool_calls[0].arguments == {"order_id": "9999"}
    assert len(response1.tool_calls) == 1
    assert len(response2.tool_calls) == 1


@pytest.mark.asyncio
async def test_crewai_adapter_captures_tool_error_via_event_bus() -> None:

    from crewai.events import crewai_event_bus
    from crewai.events.types.tool_usage_events import ToolUsageErrorEvent

    class _ErroringCrew(_FakeCrew):
        async def akickoff(self, inputs: dict) -> _FakeOutput:
            crewai_event_bus.emit(
                None, ToolUsageErrorEvent(tool_name="flaky_tool", tool_args={}, error="boom")
            )
            return _FakeOutput()

    _install_fake_module("fake_crewai_project7", build_crew=lambda: _ErroringCrew())
    adapter = CrewAIAdapter("fake_crewai_project7:build_crew")
    response = await adapter.run("hi", {})
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "flaky_tool"
    assert response.tool_calls[0].error == "boom"


def test_missing_tool_events_module_degrades_gracefully(monkeypatch) -> None:
    """If the installed crewai version lacks the event bus module, the
    adapter must not crash — it should just report tool_calls: []."""
    from agenci.adapters import crewai_adapter as module

    monkeypatch.setattr(module, "_try_import_tool_events", lambda: None)
    adapter = CrewAIAdapter.__new__(CrewAIAdapter)
    adapter._events = None
    sink: list = []
    unsubscribe = adapter._subscribe_tool_events(sink)
    unsubscribe()  # must not raise
    assert sink == []
