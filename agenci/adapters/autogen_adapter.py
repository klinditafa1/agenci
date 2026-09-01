"""Adapter for AutoGen agents and teams (``autogen-agentchat``).

``entrypoint`` resolves to a zero-argument factory that builds and
returns anything implementing AutoGen's ``TaskRunner`` protocol — an
``AssistantAgent``, or a multi-agent ``Team`` (e.g.
``RoundRobinGroupChat``, ``SelectorGroupChat``). Both expose the same
``async def run(*, task: str) -> TaskResult`` interface, so this one
adapter covers single agents and teams uniformly.

Tool calls are extracted from the real ``ToolCallRequestEvent`` /
``ToolCallExecutionEvent`` messages AutoGen emits during a run — not
inferred from the final answer — so `policy:`-based security tests
work the same way they do against the ``langchain`` adapter. Token
usage is summed from each message's ``models_usage``.

**State isolation between test cases**: an ``AssistantAgent``/``Team``
built once by the factory keeps conversation state across calls by
default, which would silently leak one test case's context into the
next if left alone. This adapter resets the runner
(`.reset()`/`.on_reset()`, whichever the object exposes) before every
test case, so each `agenci test` case starts from a clean slate. See
docs/adapters.md#autogen.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from agenci.adapters.base import AgentResponse, ToolCallRecord


class AutoGenAdapterError(Exception):
    pass


def _load_entrypoint(entrypoint: str) -> Any:
    module_path, _, attr_path = entrypoint.partition(":")
    if not attr_path:
        raise AutoGenAdapterError(f"Invalid entrypoint {entrypoint!r}; expected 'module.path:callable_name'")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise AutoGenAdapterError(f"Could not import module {module_path!r}: {exc}") from exc

    target: Any = module
    for part in attr_path.split("."):
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            raise AutoGenAdapterError(f"'{attr_path}' not found on module {module_path!r}: {exc}") from exc
    return target


def _extract_output(messages: list[Any]) -> str:
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", last)
    if isinstance(content, str):
        return content
    return str(content)


def _extract_tool_calls(messages: list[Any]) -> list[ToolCallRecord]:
    """Pairs ToolCallRequestEvent/ToolCallExecutionEvent messages by call_id."""
    requests: dict[str, Any] = {}
    calls: list[ToolCallRecord] = []

    for msg in messages:
        msg_type = type(msg).__name__
        if msg_type == "ToolCallRequestEvent":
            for call in getattr(msg, "content", []):
                requests[call.id] = call
        elif msg_type == "ToolCallExecutionEvent":
            for result in getattr(msg, "content", []):
                call = requests.get(result.call_id)
                calls.append(
                    ToolCallRecord(
                        tool=(call.name if call is not None else result.name),
                        arguments=_parse_arguments(call.arguments) if call is not None else {},
                        result=result.content,
                        error=result.content if getattr(result, "is_error", False) else None,
                    )
                )
    return calls


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}
    return {}


def _extract_token_usage(messages: list[Any]) -> tuple[int | None, int | None]:
    input_tokens = 0
    output_tokens = 0
    found = False
    for msg in messages:
        usage = getattr(msg, "models_usage", None)
        if usage is not None:
            found = True
            input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            output_tokens += getattr(usage, "completion_tokens", 0) or 0
    if not found:
        return None, None
    return input_tokens, output_tokens


class AutoGenAdapter:
    """Calls an AutoGen agent or team and normalizes the result."""

    def __init__(self, entrypoint: str, timeout_seconds: float = 120.0) -> None:
        try:
            import autogen_agentchat  # noqa: F401
        except ImportError as exc:
            raise AutoGenAdapterError(
                "The 'autogen' adapter requires autogen-agentchat. "
                "Install it with: pip install 'agenci[autogen]'"
            ) from exc

        self.entrypoint = entrypoint
        self.timeout_seconds = timeout_seconds
        self._runner = self._build_runner(_load_entrypoint(entrypoint))

    def _build_runner(self, target: Any) -> Any:
        if callable(target) and not hasattr(target, "run"):
            try:
                param_count = len(inspect.signature(target).parameters)
            except (ValueError, TypeError):
                param_count = 0
            if param_count == 0:
                return target()
        return target

    async def _reset(self) -> None:
        """Best-effort state reset between test cases (see module docstring)."""
        reset: Any = getattr(self._runner, "reset", None)
        if callable(reset):
            try:
                result = reset()
                if inspect.isawaitable(result):
                    await result
                return
            except TypeError:
                pass

        on_reset: Any = getattr(self._runner, "on_reset", None)
        if callable(on_reset):
            from autogen_core import CancellationToken

            try:
                result = on_reset(CancellationToken())
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001 - reset is best-effort, never fatal
                pass

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        if not hasattr(self._runner, "run"):
            return AgentResponse(
                output="",
                error=(
                    f"Entrypoint {self.entrypoint!r} did not resolve to an AutoGen "
                    f"agent or team (no .run() method found)."
                ),
            )

        await self._reset()

        try:
            result = await self._runner.run(task=input)
        except Exception as exc:  # noqa: BLE001 - surfaced as a test failure, not a crash
            return AgentResponse(output="", error=f"{type(exc).__name__}: {exc}")

        messages = list(getattr(result, "messages", []))
        output = _extract_output(messages)
        tool_calls = _extract_tool_calls(messages)
        input_tokens, output_tokens = _extract_token_usage(messages)

        return AgentResponse(
            output=output,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider="autogen",
            raw=result,
        )

    async def aclose(self) -> None:
        return None
