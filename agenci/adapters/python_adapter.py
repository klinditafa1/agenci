"""Adapter for calling a plain Python agent function directly in-process.

This is the lowest-friction adapter: it works with any Python callable
of the shape ``fn(input: str, context: dict) -> str | dict``, so it
covers hand-rolled agents as well as thin wrappers around LangChain,
LangGraph, CrewAI, AutoGen, etc. without Agenci depending on any of
those packages.
"""

from __future__ import annotations

import importlib
import inspect
import time
from typing import Any

from agenci.adapters.base import AgentResponse, ToolCallRecord


class PythonAdapterError(Exception):
    pass


def _load_entrypoint(entrypoint: str):
    module_path, _, attr_path = entrypoint.partition(":")
    if not attr_path:
        raise PythonAdapterError(f"Invalid entrypoint {entrypoint!r}; expected 'module.path:callable_name'")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise PythonAdapterError(f"Could not import module {module_path!r}: {exc}") from exc

    target: Any = module
    for part in attr_path.split("."):
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            raise PythonAdapterError(f"'{attr_path}' not found on module {module_path!r}: {exc}") from exc

    # Support factories: `create_agent` returning a callable/object with .run()/.invoke()
    if inspect.isfunction(target) or inspect.ismethod(target):
        return target
    if callable(target):
        return target
    raise PythonAdapterError(f"Entrypoint {entrypoint!r} did not resolve to a callable")


class PythonAdapter:
    """Calls a local Python function or agent factory."""

    def __init__(self, entrypoint: str, timeout_seconds: float = 60.0) -> None:
        self.entrypoint = entrypoint
        self.timeout_seconds = timeout_seconds
        self._fn = _load_entrypoint(entrypoint)
        # If the entrypoint is a factory (zero-arg callable returning an
        # object with .run/.invoke/__call__), resolve the actual callable once.
        self._resolved = self._resolve_callable(self._fn)

    def _resolve_callable(self, fn: Any) -> Any:
        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            return fn
        # A zero-parameter callable is treated as a factory that builds the agent.
        if len(sig.parameters) == 0:
            built = fn()
            for attr in ("run", "invoke", "__call__"):
                candidate = getattr(built, attr, None)
                if callable(candidate) and attr != "__call__":
                    return candidate
            if callable(built):
                return built
            raise PythonAdapterError(
                f"Factory {self.entrypoint!r} returned a non-callable object with no .run()/.invoke() method"
            )
        return fn

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        context = context or {}
        start = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(self._resolved):
                result = await self._resolved(input, context)
            else:
                result = self._resolved(input, context)
        except TypeError:
            # Fall back to single-argument call signatures.
            if inspect.iscoroutinefunction(self._resolved):
                result = await self._resolved(input)
            else:
                result = self._resolved(input)
        except Exception as exc:  # noqa: BLE001 - surfaced as a test failure, not a crash
            return AgentResponse(output="", error=f"{type(exc).__name__}: {exc}")

        latency_ms = (time.perf_counter() - start) * 1000
        return _normalize(result, latency_ms)

    async def aclose(self) -> None:
        return None


def _normalize(result: Any, latency_ms: float) -> AgentResponse:
    if isinstance(result, AgentResponse):
        return result
    if isinstance(result, str):
        return AgentResponse(output=result)
    if isinstance(result, dict):
        tool_calls = [ToolCallRecord(**tc) for tc in result.get("tool_calls", [])]
        return AgentResponse(
            output=str(result.get("output", "")),
            tool_calls=tool_calls,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            model=result.get("model"),
            provider=result.get("provider"),
            raw=result,
        )
    return AgentResponse(output=str(result))
