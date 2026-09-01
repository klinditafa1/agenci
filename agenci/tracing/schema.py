"""Provider-neutral agent execution trace schema.

This schema is intentionally close to the shape of an OpenTelemetry span
tree (a root span with typed children carrying attributes) so that a
future OTel exporter can be added without changing how traces are
produced elsewhere in the codebase. See docs/architecture.md.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex


class ModelCall(BaseModel):
    """A single call to an LLM."""

    kind: Literal["model_call"] = "model_call"
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A single tool invocation made by the agent."""

    kind: Literal["tool_call"] = "tool_call"
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    latency_ms: float | None = None
    error: str | None = None


TraceEvent = ModelCall | ToolCall


class AgentTrace(BaseModel):
    """A structured, provider-neutral record of a single agent run."""

    run_id: str = Field(default_factory=new_id)
    test_name: str
    timestamp: float = Field(default_factory=time.time)

    input: str
    context: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None

    events: list[ModelCall | ToolCall] = Field(default_factory=list)

    latency_ms: float | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    error: str | None = None

    # Populated after evaluation / security scanning run against this trace.
    evaluator_results: list[dict[str, Any]] = Field(default_factory=list)
    security_findings: list[dict[str, Any]] = Field(default_factory=list)

    def tool_names_used(self) -> list[str]:
        return [e.tool for e in self.events if isinstance(e, ToolCall)]

    def record_model_call(self, call: ModelCall) -> None:
        self.events.append(call)
        self.total_input_tokens += call.input_tokens or 0
        self.total_output_tokens += call.output_tokens or 0
        self.estimated_cost_usd += call.estimated_cost_usd or 0.0

    def record_tool_call(self, call: ToolCall) -> None:
        self.events.append(call)
