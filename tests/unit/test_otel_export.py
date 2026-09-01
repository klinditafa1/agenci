from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from agenci.config.models import TracingConfig  # noqa: E402
from agenci.tracing.otel_export import (  # noqa: E402
    OTelExportError,
    build_tracer_provider,
    export_agent_trace,
)
from agenci.tracing.schema import AgentTrace, ModelCall, ToolCall  # noqa: E402


@pytest.fixture
def in_memory_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("agenci-test")
    yield tracer, exporter
    provider.shutdown()


def _sample_trace() -> AgentTrace:
    trace = AgentTrace(test_name="cancel_subscription", input="cancel my sub", context={})
    trace.output = "Your subscription is cancelled."
    trace.latency_ms = 120.0
    trace.record_model_call(
        ModelCall(
            provider="openai-compatible",
            model="gpt-4.1-mini",
            latency_ms=90.0,
            input_tokens=50,
            output_tokens=20,
            estimated_cost_usd=0.0002,
        )
    )
    trace.record_tool_call(
        ToolCall(tool="cancel_subscription_tool", arguments={"user_id": "u1"}, latency_ms=25.0)
    )
    return trace


def test_export_creates_root_and_child_spans(in_memory_tracer) -> None:
    tracer, exporter = in_memory_tracer
    export_agent_trace(tracer, _sample_trace())

    spans = exporter.get_finished_spans()
    assert len(spans) == 3  # root + model_call + tool_call

    root = next(s for s in spans if s.name == "cancel_subscription")
    model_span = next(s for s in spans if s.name.startswith("model_call:"))
    tool_span = next(s for s in spans if s.name.startswith("tool_call:"))

    assert root.attributes["agenci.test_name"] == "cancel_subscription"
    assert root.attributes["gen_ai.usage.input_tokens"] == 50
    assert root.attributes["gen_ai.usage.output_tokens"] == 20

    assert model_span.parent.span_id == root.context.span_id
    assert tool_span.parent.span_id == root.context.span_id

    assert model_span.attributes["gen_ai.request.model"] == "gpt-4.1-mini"
    assert tool_span.attributes["agenci.tool.name"] == "cancel_subscription_tool"
    assert tool_span.attributes["agenci.tool.argument.user_id"] == "u1"


def test_span_durations_reflect_event_latency(in_memory_tracer) -> None:
    tracer, exporter = in_memory_tracer
    export_agent_trace(tracer, _sample_trace())

    spans = {s.name.split(":")[0]: s for s in exporter.get_finished_spans()}
    model_span = spans["model_call"]
    tool_span = spans["tool_call"]

    model_duration_ms = (model_span.end_time - model_span.start_time) / 1_000_000
    tool_duration_ms = (tool_span.end_time - tool_span.start_time) / 1_000_000
    assert round(model_duration_ms, 1) == 90.0
    assert round(tool_duration_ms, 1) == 25.0
    # The tool span starts where the model span ended (sequential layout).
    assert tool_span.start_time == model_span.end_time


def test_error_trace_sets_error_status(in_memory_tracer) -> None:
    tracer, exporter = in_memory_tracer
    trace = AgentTrace(test_name="broken", input="hi", context={})
    trace.error = "agent crashed"
    trace.latency_ms = 5.0
    export_agent_trace(tracer, trace)

    root = exporter.get_finished_spans()[0]
    assert root.status.status_code.name == "ERROR"


def test_build_tracer_provider_requires_export_target() -> None:
    with pytest.raises(OTelExportError):
        build_tracer_provider(TracingConfig(enabled=True))


def test_build_tracer_provider_with_console() -> None:
    provider = build_tracer_provider(TracingConfig(enabled=True, console=True))
    assert provider is not None
    provider.shutdown()


def test_build_tracer_provider_with_otlp_endpoint() -> None:
    provider = build_tracer_provider(
        TracingConfig(enabled=True, otlp_endpoint="http://localhost:4318/v1/traces")
    )
    assert provider is not None
    provider.shutdown()
