# Architecture

## Layout

```text
agenci/
    cli/            Typer app: init, test, security, evaluate, diff, report, pr-comment, dashboard, config, version
    core/            Test-case models, assertion engine, cost estimator, TestRunner (the execution engine)
    adapters/        AgentAdapter protocol + python/http/openai/langchain/crewai/mcp/autogen implementations + registry
    evaluators/      JudgeProvider protocol + mock/openai implementations + evaluation engine
    security/        Policy engine (tool authorization, output patterns) + severity-weighted scoring
    tracing/         Provider-neutral AgentTrace schema (OTel-shaped) + OpenTelemetry span export
    storage/         StorageBackend protocol + SQLite implementation
    config/          Pydantic schema for agenci.yaml + loader with readable validation errors
    reporting/       Metrics aggregation, baseline-vs-current diff, console/JSON rendering
    dashboard/        Zero-dependency local dashboard (stdlib http.server)
    integrations/    GitHub PR comment posting/updating (github.py); reserved for future integrations
```

## Data flow

```text
agenci.yaml + tests/*.yaml
        │
        ▼
   TestCase[]  (agenci/core/models.py, loaded by core/test_loader.py)
        │
        ▼
   AgentAdapter.run(input, context)  →  AgentResponse   (adapters/)
        │
        ├─→ AgentTrace (model calls, tool calls, tokens, cost)   (tracing/)
        │
        ├─→ run_assertion() for each Assertion                   (core/assertions.py)
        ├─→ run_evaluation() via JudgeProvider, if declared       (evaluators/)
        └─→ evaluate_policy() via SecurityPolicy, if declared      (security/policy.py)
                │
                ▼
           TestOutcome  (core/models.py)
                │
                ▼
   build_report()  →  TestReport  (metrics + security score)      (reporting/builder.py)
                │
        ┌───────┴────────┐
        ▼                ▼
  SqliteStorage      console/JSON rendering
   (storage/)          (reporting/console.py)
        │
        ▼
   compare_reports(baseline, current)  →  RegressionReport         (reporting/diff.py)
```

Everything downstream of `AgentResponse` is provider- and
framework-neutral: adding a new adapter or judge provider never
requires touching the test runner, reporting, storage, or CLI.

## Why a `Protocol`-based design

`AgentAdapter`, `JudgeProvider`, and `StorageBackend` are all
`typing.Protocol`s, not abstract base classes. This keeps adding a new
implementation to a single new file plus one line in the relevant
registry (`adapters/registry.py`, `evaluators/engine.py`) — see
[extending-agenci.md](extending-agenci.md).

## Tracing

`agenci/tracing/schema.py` defines `AgentTrace` as a root record with a
flat list of `ModelCall` / `ToolCall` events — deliberately close to
the shape of an OpenTelemetry span tree (a root span, typed children
with attributes). `agenci/tracing/otel_export.py` implements that
mapping directly: one `AgentTrace` → one root span, each
`ModelCall`/`ToolCall` → a child span with `gen_ai.*`-convention
attributes, exported via OTLP/HTTP or to the console. See
[observability.md](observability.md) for configuration and exactly
what's exported.

## Cost tracking

All pricing logic lives in `agenci/core/cost.py`'s `CostEstimator` — a
`{model: $/1M tokens}` registry with a small set of built-in defaults,
overridable via `cost.models` in `agenci.yaml`. Nothing else in the
codebase computes a dollar figure; every cost number in a report
traces back to this one class, and every cost figure is a labeled
*estimate*, not an invoice reconciliation.

## Storage

`agenci/storage/base.py` defines `StorageBackend` as a narrow protocol
(`save_run`, `get_run`, `list_runs`, `latest_run`, `close`).
`SqliteStorage` is the open-source implementation (stdlib `sqlite3`
only, migrations via idempotent `CREATE TABLE IF NOT EXISTS` +
`PRAGMA user_version`). A future **Agenci Cloud** PostgreSQL backend
implements the same protocol; nothing in the CLI, dashboard, or
reporting layer would need to change.

## Local dashboard

`agenci/dashboard/server.py` is intentionally the least-invested part
of the codebase, per the product principle "the dashboard is not the
main product." It's a `http.server.ThreadingHTTPServer` that reads
directly from `SqliteStorage` on every request and renders plain HTML
— no build step, no JS framework, no extra dependency.

## Roadmap

**v0.2 (complete)** — `langchain` (LangChain/LangGraph, via `Runnable`
+ a callback handler for real tool-call/token tracing), `crewai` (via
CrewAI's own event bus for real tool-call tracing), `mcp` (client-side,
calls a tool on a stdio MCP server; verified end-to-end against
`mcp==1.9.4`), `autogen` (agents and teams, with real tool-call tracing
via AutoGen's own event messages and automatic conversation-state
reset between test cases), and `anthropic` (Messages API, no SDK
dependency) adapters have all landed — see [adapters.md](adapters.md)
for exactly what each does and doesn't cover yet.
OpenTelemetry export (`tracing/otel_export.py`, see
[observability.md](observability.md)) and GitHub PR comments
(`integrations/github.py`, `agenci pr-comment`, see
[github-actions.md](github-actions.md#pr-comments)) are done. The
security framework grew `required_tools`, a data-exfiltration
heuristic (`sensitive_tools` + `block_input_echo_to_sensitive_tools`),
and built-in sensitive-data pattern scanning (`check_pii_leakage`) —
see [security.md](security.md#categories). Regression analytics grew
per-test (`newly_failing`/`newly_passing`/`tests_added`/`tests_removed`)
and per-security-category diffing, surfaced in both the console report
and GitHub PR comments — see
[regression-testing.md](regression-testing.md#what-gets-compared).

**v0.3** — Agenci Cloud: accounts, organizations, remote runs,
centralized history, hosted dashboards.

**v0.4** — production monitoring, continuous evaluation, scheduled
security testing, advanced traces, alerting.

**v1.0** — enterprise RBAC, SSO, policy engine, audit logs, private
deployments, organization-wide agent governance.
