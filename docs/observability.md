# Observability: OpenTelemetry export

Every `agenci test`/`agenci security`/`agenci evaluate` run produces a
structured, provider-neutral `AgentTrace` per test case — model calls,
tool calls, tokens, cost, errors (see
[architecture.md#tracing](architecture.md#tracing)). Agenci can export
these as OpenTelemetry spans to any OTLP-compatible backend (Jaeger,
Tempo, an OTel Collector, a vendor's OTLP ingest endpoint, ...), so
your CI test runs show up alongside your production agent traces.

## Install

```bash
pip install 'agenci[otel]'
```

## Configure

```yaml
tracing:
  enabled: true
  otlp_endpoint: "http://localhost:4318/v1/traces"   # or set OTEL_EXPORTER_OTLP_ENDPOINT
  console: false                                        # also print spans, for debugging
  service_name: agenci
```

`otlp_endpoint` can be omitted if the standard
`OTEL_EXPORTER_OTLP_ENDPOINT` environment variable is set instead —
useful if your CI already configures OTel centrally. If
`tracing.enabled: true` but neither `otlp_endpoint` nor `console` nor
the env var is set, Agenci fails fast with a clear error rather than
silently exporting nothing.

Run normally — export happens automatically after the suite completes:

```bash
agenci test
```

## What gets exported

One root span per test case, named after the test, with child spans
for every model call and tool call the agent made during that test:

```text
cancel_subscription                    (root span)
├── model_call:gpt-4.1-mini            (child span)
└── tool_call:cancel_subscription_tool (child span)
```

| Attribute | On | Meaning |
|---|---|---|
| `agenci.run_id`, `agenci.test_name` | root | Identifies the run/test. |
| `agenci.input_length`, `agenci.output_length` | root | Character counts (not the raw text — see below). |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | root, model_call | Following the [OTel GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) naming. |
| `agenci.estimated_cost_usd` | root, model_call | From Agenci's cost estimator — see [architecture.md#cost-tracking](architecture.md#cost-tracking). |
| `gen_ai.system`, `gen_ai.request.model` | model_call | Provider and model name. |
| `agenci.tool.name`, `agenci.tool.argument.<key>` | tool_call | Tool name and each argument, stringified. |

**Agenci does not export raw test input/output text as span
attributes** — only lengths — to avoid silently exporting potentially
sensitive prompts/completions to a telemetry backend. If you need the
full text, use `agenci test --json --output report.json`, which
includes it explicitly (your own retention/access controls apply to
that file, not to a telemetry pipeline).

## Timing accuracy

`AgentTrace` records each event's own latency but not absolute
wall-clock start times, so child span timestamps are laid out
sequentially from the test's start time. **Span durations are
accurate**; span **offsets/ordering** are a best-effort approximation
when an agent made calls concurrently rather than sequentially.

## Local testing without a real collector

```yaml
tracing:
  enabled: true
  console: true
```

Prints each exported span as JSON to stdout — useful for confirming
the shape of what would be exported before pointing at a real
collector.
