"""Adapter for CrewAI crews.

``entrypoint`` resolves to a zero-argument factory that builds and
returns a ``crewai.Crew`` (this mirrors how CrewAI projects are
typically structured — a ``build_crew()`` function assembling agents,
tasks, and tools). Agenci calls ``crew.kickoff_async()``/``akickoff()``
with the test's ``input`` bound to a configurable inputs key, and
normalizes the ``CrewOutput`` into an ``AgentResponse``.

Tool-call visibility uses CrewAI's own event bus
(``crewai.events.crewai_event_bus``): the adapter subscribes to
``ToolUsageFinishedEvent``/``ToolUsageErrorEvent`` for the duration of
each call and unsubscribes immediately after, so tool calls are
observed directly from CrewAI's own instrumentation rather than
inferred from the final answer — the same guarantee the ``langchain``
and ``autogen`` adapters provide. If the installed CrewAI version
predates this event bus, the adapter degrades gracefully to
``tool_calls: []`` rather than failing. Token usage is reliably
available via ``CrewOutput.token_usage`` and is reported accurately
either way.
"""

from __future__ import annotations

import importlib
import inspect
import time
from typing import Any

from agenci.adapters.base import AgentResponse, ToolCallRecord


class CrewAIAdapterError(Exception):
    pass


def _load_entrypoint(entrypoint: str) -> Any:
    module_path, _, attr_path = entrypoint.partition(":")
    if not attr_path:
        raise CrewAIAdapterError(f"Invalid entrypoint {entrypoint!r}; expected 'module.path:callable_name'")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise CrewAIAdapterError(f"Could not import module {module_path!r}: {exc}") from exc

    target: Any = module
    for part in attr_path.split("."):
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            raise CrewAIAdapterError(f"'{attr_path}' not found on module {module_path!r}: {exc}") from exc
    return target


def _try_import_tool_events() -> tuple[Any, Any, Any] | None:
    """Returns (event_bus, ToolUsageFinishedEvent, ToolUsageErrorEvent), or
    None if the installed crewai version doesn't expose this event bus."""
    try:
        from crewai.events import crewai_event_bus
        from crewai.events.types.tool_usage_events import (
            ToolUsageErrorEvent,
            ToolUsageFinishedEvent,
        )
    except ImportError:
        return None
    return crewai_event_bus, ToolUsageFinishedEvent, ToolUsageErrorEvent


class CrewAIAdapter:
    def __init__(
        self,
        entrypoint: str,
        input_key: str = "input",
        timeout_seconds: float = 300.0,
    ) -> None:
        try:
            import crewai  # noqa: F401
        except ImportError as exc:
            raise CrewAIAdapterError(
                "The 'crewai' adapter requires the crewai package. "
                "Install it with: pip install 'agenci[crewai]'"
            ) from exc

        self.entrypoint = entrypoint
        self.input_key = input_key
        self.timeout_seconds = timeout_seconds
        self._factory = _load_entrypoint(entrypoint)
        self._events = _try_import_tool_events()

    def _build_crew(self) -> Any:
        target = self._factory
        if callable(target):
            param_count = 0
            try:
                param_count = len(inspect.signature(target).parameters)
            except (ValueError, TypeError):
                pass
            if param_count == 0:
                return target()
            return target
        return target  # already a Crew instance

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        context = context or {}
        crew = self._build_crew()
        if not hasattr(crew, "kickoff") and not hasattr(crew, "akickoff"):
            return AgentResponse(
                output="",
                error=(
                    f"Entrypoint {self.entrypoint!r} did not resolve to a CrewAI Crew "
                    f"(no .kickoff()/.akickoff() method found)."
                ),
            )

        inputs = {self.input_key: input, **context}

        tool_calls: list[ToolCallRecord] = []
        unsubscribe = self._subscribe_tool_events(tool_calls)

        start = time.perf_counter()
        try:
            try:
                if hasattr(crew, "akickoff"):
                    result = await crew.akickoff(inputs=inputs)
                elif hasattr(crew, "kickoff_async"):
                    result = await crew.kickoff_async(inputs=inputs)
                else:
                    # Older/sync-only CrewAI versions: kickoff() is blocking.
                    import asyncio

                    result = await asyncio.to_thread(crew.kickoff, inputs=inputs)
            except Exception as exc:  # noqa: BLE001 - surfaced as a test failure, not a crash
                return AgentResponse(output="", error=f"{type(exc).__name__}: {exc}", tool_calls=tool_calls)
        finally:
            # CrewAI dispatches event handlers via a background thread pool
            # (emit() does not block), so tool-usage events for this run can
            # still be in flight when akickoff() returns. flush() blocks
            # until every handler scheduled so far has actually run, so
            # `tool_calls` is complete before we unsubscribe and read it.
            if self._events is not None:
                self._events[0].flush(timeout=5.0)
            unsubscribe()
        _ = (time.perf_counter() - start) * 1000  # latency also measured by the caller

        output = str(getattr(result, "raw", result))
        input_tokens: int | None = None
        output_tokens: int | None = None
        usage = getattr(result, "token_usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)

        return AgentResponse(
            output=output,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider="crewai",
            raw=result,
        )

    def _subscribe_tool_events(self, sink: list[ToolCallRecord]):
        """Subscribes to CrewAI's tool-usage events for one run and returns
        an unsubscribe callback. No-ops if the installed CrewAI version
        doesn't expose the event bus (older releases)."""
        if self._events is None:
            return lambda: None

        event_bus, ToolUsageFinishedEvent, ToolUsageErrorEvent = self._events

        def on_finished(source: Any, event: Any) -> None:
            args = event.tool_args if isinstance(event.tool_args, dict) else {"raw": event.tool_args}
            sink.append(ToolCallRecord(tool=event.tool_name, arguments=args, result=event.output))

        def on_error(source: Any, event: Any) -> None:
            args = event.tool_args if isinstance(event.tool_args, dict) else {"raw": event.tool_args}
            sink.append(ToolCallRecord(tool=event.tool_name, arguments=args, error=str(event.error)))

        event_bus.on(ToolUsageFinishedEvent)(on_finished)
        event_bus.on(ToolUsageErrorEvent)(on_error)

        def unsubscribe() -> None:
            event_bus.off(ToolUsageFinishedEvent, on_finished)
            event_bus.off(ToolUsageErrorEvent, on_error)

        return unsubscribe

    async def aclose(self) -> None:
        return None
