"""Provider-neutral agent adapter interface.

Agenci's core engine never talks to an agent framework directly. It
only ever calls ``AgentAdapter.run(...)``. This is the seam that lets
Agenci stay framework-neutral: adding support for LangGraph, CrewAI,
MCP, etc. means writing a new adapter that implements this protocol —
nothing else in the codebase needs to change.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """A tool call reported by the agent under test.

    Adapters populate this on a best-effort basis: a Python adapter can
    report exact tool calls if the wrapped agent exposes them; an HTTP
    adapter can only report what the remote service chooses to return
    in its response payload.
    """

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    latency_ms: float | None = None
    error: str | None = None


class AgentResponse(BaseModel):
    """The normalized result of a single agent invocation."""

    output: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    provider: str | None = None
    raw: Any = None
    error: str | None = None


@runtime_checkable
class AgentAdapter(Protocol):
    """Interface every Agenci adapter must implement."""

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        """Invoke the agent under test once and return a normalized response."""
        ...

    async def aclose(self) -> None:
        """Release any resources (HTTP clients, etc.). Safe to call multiple times."""
        ...
