"""Adapter for LangChain / LangGraph agents (any ``Runnable``).

Rather than depending on the full ``langchain`` metapackage, this
adapter only requires ``langchain-core`` — the interfaces (``Runnable``,
callbacks) that LangChain, LangGraph, and most LCEL-based agents all
share. A LangGraph compiled graph is itself a ``Runnable``, so this one
adapter covers both.

Tool calls and token usage are captured via a ``BaseCallbackHandler``
attached to the invocation, not guessed from the output text — this is
what lets Agenci's security framework see *actual* tool invocations
made during a run, not just the final answer.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from agenci.adapters.base import AgentResponse, ToolCallRecord


class LangChainAdapterError(Exception):
    pass


def _load_runnable(entrypoint: str) -> Any:
    module_path, _, attr_path = entrypoint.partition(":")
    if not attr_path:
        raise LangChainAdapterError(
            f"Invalid entrypoint {entrypoint!r}; expected 'module.path:callable_name'"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise LangChainAdapterError(f"Could not import module {module_path!r}: {exc}") from exc

    target: Any = module
    for part in attr_path.split("."):
        try:
            target = getattr(target, part)
        except AttributeError as exc:
            raise LangChainAdapterError(f"'{attr_path}' not found on module {module_path!r}: {exc}") from exc

    # Support factories: a zero-arg callable that builds and returns the Runnable.
    if callable(target) and not hasattr(target, "invoke"):
        try:
            built = target()
        except TypeError as exc:
            raise LangChainAdapterError(
                f"Entrypoint {entrypoint!r} is callable but not a Runnable, and calling it "
                f"as a zero-argument factory failed: {exc}"
            ) from exc
        target = built

    if not hasattr(target, "invoke") and not hasattr(target, "ainvoke"):
        raise LangChainAdapterError(
            f"Entrypoint {entrypoint!r} did not resolve to a LangChain Runnable "
            f"(no .invoke()/.ainvoke() method found)."
        )
    return target


def _make_callback_handler():
    """Builds a langchain-core BaseCallbackHandler that records tool calls
    and token usage without requiring the caller to import langchain-core
    at module load time (kept as an optional dependency)."""
    from langchain_core.callbacks import BaseCallbackHandler

    class _TracingCallbackHandler(BaseCallbackHandler):
        def __init__(self) -> None:
            self.tool_calls: list[ToolCallRecord] = []
            self.input_tokens = 0
            self.output_tokens = 0
            self.model_name: str | None = None
            self._tool_starts: dict[Any, float] = {}

        def on_tool_start(self, serialized, input_str, *, run_id=None, **kwargs) -> None:  # noqa: ANN001
            self._tool_starts[run_id] = time.perf_counter()

        def on_tool_end(self, output, *, run_id=None, **kwargs) -> None:  # noqa: ANN001
            start = self._tool_starts.pop(run_id, None)
            latency_ms = (time.perf_counter() - start) * 1000 if start is not None else None
            tool_name = kwargs.get("name") or "unknown_tool"
            self.tool_calls.append(
                ToolCallRecord(tool=tool_name, arguments={}, result=str(output), latency_ms=latency_ms)
            )

        def on_tool_error(self, error, *, run_id=None, **kwargs) -> None:  # noqa: ANN001
            start = self._tool_starts.pop(run_id, None)
            latency_ms = (time.perf_counter() - start) * 1000 if start is not None else None
            tool_name = kwargs.get("name") or "unknown_tool"
            self.tool_calls.append(
                ToolCallRecord(tool=tool_name, arguments={}, latency_ms=latency_ms, error=str(error))
            )

        def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001
            try:
                usage = response.llm_output.get("token_usage") if response.llm_output else None
                if usage:
                    self.input_tokens += usage.get("prompt_tokens", 0) or 0
                    self.output_tokens += usage.get("completion_tokens", 0) or 0
                model_name = (response.llm_output or {}).get("model_name")
                if model_name:
                    self.model_name = model_name
            except AttributeError:
                pass

        def on_chat_model_start(self, serialized, messages, **kwargs) -> None:  # noqa: ANN001
            name = (serialized or {}).get("name") or (serialized or {}).get("id", [None])[-1]
            if name and not self.model_name:
                self.model_name = str(name)

    return _TracingCallbackHandler()


def _extract_output(result: Any, output_key: str | None) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "content"):  # a BaseMessage (AIMessage, etc.)
        return str(result.content)
    if isinstance(result, dict):
        if output_key and output_key in result:
            return str(result[output_key])
        for key in ("output", "answer", "result", "text"):
            if key in result:
                return str(result[key])
        return str(result)
    return str(result)


class LangChainAdapter:
    """Calls a LangChain/LangGraph ``Runnable`` and normalizes the result.

    ``entrypoint`` resolves either directly to a ``Runnable`` (a chain,
    an agent executor, a compiled LangGraph graph) or to a zero-argument
    factory that builds one.
    """

    def __init__(
        self,
        entrypoint: str,
        input_key: str = "input",
        output_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        try:
            from langchain_core.callbacks import BaseCallbackHandler  # noqa: F401
        except ImportError as exc:
            raise LangChainAdapterError(
                "The 'langchain' adapter requires langchain-core. "
                "Install it with: pip install 'agenci[langchain]'"
            ) from exc

        self.entrypoint = entrypoint
        self.input_key = input_key
        self.output_key = output_key
        self.timeout_seconds = timeout_seconds
        self._runnable = _load_runnable(entrypoint)

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        context = context or {}
        payload: Any
        if isinstance(context, dict) and context:
            payload = {self.input_key: input, **context}
        else:
            payload = {self.input_key: input}

        handler = _make_callback_handler()
        config = {"callbacks": [handler]}

        try:
            if hasattr(self._runnable, "ainvoke"):
                result = await self._runnable.ainvoke(payload, config=config)
            else:
                result = self._runnable.invoke(payload, config=config)
        except Exception as exc:  # noqa: BLE001 - surfaced as a test failure, not a crash
            return AgentResponse(output="", error=f"{type(exc).__name__}: {exc}")

        output = _extract_output(result, self.output_key)
        return AgentResponse(
            output=output,
            tool_calls=handler.tool_calls,
            input_tokens=handler.input_tokens or None,
            output_tokens=handler.output_tokens or None,
            model=handler.model_name,
            provider="langchain",
            raw=result,
        )

    async def aclose(self) -> None:
        return None
