"""Exports Agenci's provider-neutral :class:`AgentTrace` records as
OpenTelemetry spans.

The trace schema (``agenci/tracing/schema.py``) was deliberately kept
close to the shape of an OTel span tree — a root record with typed
child events carrying attributes — specifically so this mapping could
be this direct: one ``AgentTrace`` becomes one root span named after
the test case, and each ``ModelCall``/``ToolCall`` becomes a child
span. No other part of Agenci needed to change for this to work.

This module is written against ``opentelemetry-sdk`` only; no vendor
SDK. Point ``tracing.otlp_endpoint`` at any OTLP/HTTP-compatible
collector (Jaeger, Tempo, an OTel Collector, a vendor's OTLP ingest
endpoint, ...).
"""

from __future__ import annotations

import os
from typing import Any

from agenci.config.models import TracingConfig
from agenci.tracing.schema import AgentTrace, ModelCall, ToolCall

_GEN_AI_SYSTEM = "gen_ai.system"
_GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
_GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
_GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"


class OTelExportError(Exception):
    pass


def _require_otel():
    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.sdk.resources import Resource  # noqa: F401
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
    except ImportError as exc:
        raise OTelExportError(
            "OpenTelemetry export requires the opentelemetry SDK. Install it with: pip install 'agenci[otel]'"
        ) from exc


def build_tracer_provider(config: TracingConfig):
    """Builds a TracerProvider configured per ``tracing:`` in agenci.yaml.

    Exports to an OTLP/HTTP endpoint if one is configured (explicitly,
    or via the standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var), and/or
    to the console if ``tracing.console`` is set. Raises OTelExportError
    with an install hint if the optional SDK isn't installed.
    """
    _require_otel()

    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

    resource = Resource.create({SERVICE_NAME: config.service_name})
    provider = TracerProvider(resource=resource)

    endpoint = config.otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    if config.console:
        import sys

        # SimpleSpanProcessor exports synchronously on span.end() — no
        # background-thread flush race, which matters here since console
        # output is read immediately by the CLI's caller (or a test).
        # `out=sys.stdout` is passed explicitly because ConsoleSpanExporter's
        # default binds sys.stdout at module-import time, not at call time —
        # without this, output can silently go to a stream a caller (e.g. a
        # test harness that redirects stdout) is no longer reading from.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))

    if not endpoint and not config.console:
        # tracing.enabled=true with nothing configured to export to is
        # almost certainly a misconfiguration a user would want to know
        # about, not a silent no-op.
        raise OTelExportError(
            "tracing.enabled is true but no export target is configured. "
            "Set tracing.otlp_endpoint, tracing.console: true, or the "
            "OTEL_EXPORTER_OTLP_ENDPOINT environment variable."
        )

    return provider


def _model_call_attributes(call: ModelCall) -> dict[str, Any]:
    attrs: dict[str, Any] = {_GEN_AI_SYSTEM: call.provider, _GEN_AI_REQUEST_MODEL: call.model}
    if call.input_tokens is not None:
        attrs[_GEN_AI_USAGE_INPUT_TOKENS] = call.input_tokens
    if call.output_tokens is not None:
        attrs[_GEN_AI_USAGE_OUTPUT_TOKENS] = call.output_tokens
    if call.estimated_cost_usd is not None:
        attrs["agenci.estimated_cost_usd"] = call.estimated_cost_usd
    return attrs


def _tool_call_attributes(call: ToolCall) -> dict[str, Any]:
    attrs: dict[str, Any] = {"agenci.tool.name": call.tool}
    for key, value in call.arguments.items():
        attrs[f"agenci.tool.argument.{key}"] = str(value)
    if call.error:
        attrs["agenci.tool.error"] = call.error
    return attrs


def export_agent_trace(tracer, trace: AgentTrace) -> None:
    """Exports one AgentTrace as a root span with child spans per event.

    Per-event start times aren't recorded by AgentTrace today (only
    each event's own latency), so child span timestamps are
    approximated by laying events out sequentially from the trace's
    start time — accurate span *durations*, best-effort span
    *ordering/offsets*. See docs/observability.md.

    Spans are created and ended explicitly (not via the
    ``start_as_current_span`` context manager) so each can be given a
    precise ``end_time`` without the double-``end()`` warning that
    combining both approaches would trigger; parent/child linkage is
    established explicitly via ``set_span_in_context`` instead of
    relying on contextvars-based "current span" propagation.
    """
    from opentelemetry.trace import Status, StatusCode, set_span_in_context

    start_ns = int(trace.timestamp * 1_000_000_000)
    total_ns = int((trace.latency_ms or 0) * 1_000_000)
    end_ns = start_ns + total_ns

    root_span = tracer.start_span(
        trace.test_name,
        start_time=start_ns,
        attributes={
            "agenci.run_id": trace.run_id,
            "agenci.test_name": trace.test_name,
            "agenci.input_length": len(trace.input or ""),
            "agenci.output_length": len(trace.output or "") if trace.output else 0,
            _GEN_AI_USAGE_INPUT_TOKENS: trace.total_input_tokens,
            _GEN_AI_USAGE_OUTPUT_TOKENS: trace.total_output_tokens,
            "agenci.estimated_cost_usd": trace.estimated_cost_usd,
        },
    )
    if trace.error:
        root_span.set_status(Status(StatusCode.ERROR, trace.error))
        root_span.record_exception(RuntimeError(trace.error))

    root_context = set_span_in_context(root_span)
    cursor_ns = start_ns
    for event in trace.events:
        if isinstance(event, ModelCall):
            child_attrs = _model_call_attributes(event)
            span_name = f"model_call:{event.model}"
            latency_ns = int(event.latency_ms * 1_000_000)
        else:
            child_attrs = _tool_call_attributes(event)
            span_name = f"tool_call:{event.tool}"
            latency_ns = int((event.latency_ms or 0) * 1_000_000)

        child_end_ns = cursor_ns + latency_ns
        child_span = tracer.start_span(
            span_name, context=root_context, start_time=cursor_ns, attributes=child_attrs
        )
        if isinstance(event, ToolCall) and event.error:
            child_span.set_status(Status(StatusCode.ERROR, event.error))
        child_span.end(end_time=child_end_ns)
        cursor_ns = child_end_ns

    root_span.end(end_time=max(end_ns, cursor_ns))


def export_traces(config: TracingConfig, traces: list[AgentTrace]) -> None:
    """Builds a tracer provider from config, exports every trace, and
    flushes/shuts it down. Convenience wrapper for CLI use."""
    provider = build_tracer_provider(config)
    tracer = provider.get_tracer(config.service_name)
    for trace in traces:
        export_agent_trace(tracer, trace)
    provider.force_flush()
    provider.shutdown()
