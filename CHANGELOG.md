# Changelog

All notable changes to Agenci are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Agenci follows [Semantic Versioning](https://semver.org/) once it
reaches 1.0 — see [Versioning](#versioning) below for what that means
before then.

## [Unreleased]

## [0.2.0] - v0.2 milestone

### Added

- **Adapters**: `langchain` (LangChain/LangGraph `Runnable`s, with real
  tool-call and token tracing via a callback handler), `crewai` (with
  real tool-call tracing via CrewAI's own event bus), `mcp`
  (client-side — launches a stdio MCP server and calls a configured
  tool), `autogen` (agents and teams, with real tool-call tracing and
  automatic conversation-state reset between test cases), `anthropic`
  (Messages API, no SDK dependency).
- **OpenTelemetry export** (`tracing/otel_export.py`): maps every
  `AgentTrace` to a root span with child spans per model/tool call,
  exportable via OTLP/HTTP or to the console. See
  [docs/observability.md](docs/observability.md).
- **GitHub PR comments** (`agenci pr-comment`, `integrations/github.py`):
  posts/updates a summary comment on a pull request, matched by a
  hidden marker so re-runs update rather than duplicate. Wired into
  the composite GitHub Action. See
  [docs/github-actions.md](docs/github-actions.md#pr-comments).
- **Richer security checks**: `policy.required_tools` (tools that must
  be called), `policy.sensitive_tools` +
  `policy.block_input_echo_to_sensitive_tools` (a data-exfiltration
  heuristic), `policy.check_pii_leakage` + `policy.max_output_length`
  (built-in sensitive-data pattern scanning). See
  [docs/security.md](docs/security.md#categories).
- **Improved regression analytics**: `agenci diff` now reports
  per-test analytics (`newly_failing`, `newly_passing`, `tests_added`,
  `tests_removed`) and per-security-category score deltas, surfaced in
  both the console report and PR comments. New opt-in
  `thresholds.regression.fail_on_any_newly_failing`. See
  [docs/regression-testing.md](docs/regression-testing.md#what-gets-compared).
- **Concurrent test execution**: `agenci test --concurrency N` (or
  `execution.concurrency` in `agenci.yaml`) runs up to `N` test cases
  at once. Automatically clamped to `1` for adapters (`autogen`,
  `crewai`) that hold state concurrent calls would corrupt. See
  [docs/adapters.md](docs/adapters.md#a-note-on-concurrency).

### Fixed

- `mcp` adapter: the reference example and docs previously targeted an
  unreleased `mcp==2.0.0` API shape that hung on stdio transport; both
  now target the stable, widely-installed `mcp` 1.x line
  (`mcp.server.fastmcp.FastMCP`), verified end-to-end against
  `mcp==1.9.4` in a clean environment. The `mcp` extra now pins
  `mcp>=1.0,<2.0`.
- `crewai` adapter: a race condition where a call's own tool-usage
  events (dispatched by CrewAI on a background thread pool) could
  still be in flight when the call returned, occasionally attributing
  tool calls to the wrong test case — fixed by flushing CrewAI's event
  bus before reading collected tool calls.

### Security

- Documented least-privilege token scoping and the
  `pull_request_target` "pwn request" risk for the composite GitHub
  Action — see
  [docs/github-actions.md#security-considerations](docs/github-actions.md#security-considerations).
  Added an explicit `permissions:` block to the example workflow that
  uses the action.
- Added `owner/name` format validation to `agenci pr-comment --repo`.
- Audited (no changes needed): confirmed no GitHub token leakage in
  error paths for both HTTP-status and connection-failure exceptions;
  confirmed no untrusted GitHub context is interpolated into shell
  commands in the composite action.

## [0.1.0] - Initial release

### Added

- Core engine: `TestCase`/`TestOutcome` models, functional assertion
  engine (`contains`, `not_contains`, `regex`, `exact`, `json_schema`,
  `semantic_similarity`, `custom_python`), `TestRunner`.
- Adapters: `python` (local callables/factories), `http` (REST agents),
  `openai` (OpenAI-compatible chat completions, no SDK dependency).
- Evaluators: `JudgeProvider` protocol, dependency-free `mock` judge,
  `openai` judge.
- Security framework: policy-based tool authorization
  (`allowed_tools`/`forbidden_tools`/`max_tool_calls`), forbidden
  output patterns, severity-weighted scoring.
- Regression testing: baseline-vs-current diff with configurable
  thresholds on success rate, security score, cost, and latency.
- Provider-neutral `AgentTrace` schema (model calls, tool calls,
  tokens, cost) — architected to be OpenTelemetry-exportable.
- Centralized cost estimation (`CostEstimator`), SQLite storage
  (`StorageBackend` protocol), a zero-dependency local dashboard.
- CLI: `init`, `test`, `security`, `evaluate`, `diff`, `report`,
  `dashboard`, `config validate/show`, `version`.
- GitHub Actions integration: composite action + scaffolded workflow.
- Examples: `basic-agent`, `http-agent`, `openai-agent`,
  `security-testing`, `regression-testing`, `github-actions`.

## Versioning

Agenci is pre-1.0 (`0.x`). Per [SemVer's spec for initial
development](https://semver.org/#spec-item-4), a `0.x` release may
introduce breaking changes in a minor version bump (`0.1` → `0.2`) —
this changelog calls those out explicitly rather than promising
strict backward compatibility. Config schema changes are additive
wherever possible (new fields with safe defaults); a breaking config
or CLI change will be documented here and in
[docs/configuration.md](docs/configuration.md) at the time it ships.

Once Agenci reaches `1.0`, standard [SemVer](https://semver.org/)
applies: breaking changes only in major versions.
