<p align="center">
  <img src="Agenci Logo.png" alt="Agenci logo" width="400">
</p>
# Agenci

**CI/CD, evaluation and security testing for AI agents.**

Agenci is GitHub Actions for AI agents: it continuously tests, evaluates,
benchmarks, security-tests, and regression-tests AI agents and LLM
applications, so a change to a prompt, model, tool, or workflow can't
silently break — or compromise — production behavior.

```bash
pip install agenci

agenci init
agenci test
```

```text
Agenci — my-agent
2 evaluations completed

┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Suite      ┃ Passed ┃ Total ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Functional │ 2      │ 2     │ PASS   │
└────────────┴────────┴───────┴────────┘

Success rate:   100.0%
Security score: 100/100
Avg latency:    0ms
Estimated cost: $0.0000

STATUS: PASS
```

## Why Agenci exists

Traditional software is `input → deterministic output`. AI agents are:

```text
input → model → reasoning → tool calls → external systems → more model calls → output
```

A change to a prompt, model, tool, system instruction, RAG database, or
agent workflow can silently introduce regressions, hallucinations,
security vulnerabilities, tool misuse, higher cost, higher latency, or
prompt-injection vulnerabilities — with no compiler and no test suite
to catch it. Agenci is the infrastructure that catches it, in CI,
before it ships.

```text
Developer changes AI agent
        ↓
opens Pull Request
        ↓
Agenci runs evaluations
        ↓
Agenci compares against baseline
        ↓
Agenci detects regressions
        ↓
PR passes or fails
```

## What Agenci does

- **Functional testing** — assert on agent output: `contains`, `not_contains`,
  `regex`, `exact`, `json_schema`, `semantic_similarity`, or your own
  `custom_python` assertion function.
- **LLM-as-judge evaluation** — score correctness, relevance, factuality,
  instruction-following, and other criteria with a configurable judge
  provider (a dependency-free mock provider out of the box, OpenAI-compatible
  providers for real evaluation).
- **Security testing** — policy-based checks for prompt-injection resistance,
  tool authorization, excessive tool access, and output-safety violations,
  rolled up into a per-category security score.
- **Regression testing** — compare a baseline run against a current run and
  fail CI when success rate, security score, cost, or latency regress beyond
  configured thresholds.
- **Traces** — every run produces a structured, provider-neutral trace of
  model calls and tool calls, with token usage and estimated cost.
- **GitHub Actions** — run the whole suite on every PR and fail the check
  when thresholds are violated.
- **Local dashboard** — a zero-dependency view of recent runs.

## Install

```bash
pip install agenci
# or, without installing:
uvx agenci init
```

## Quickstart

```bash
agenci init      # scaffold agenci.yaml, tests/, and an example agent
agenci test      # run functional tests against the example agent
agenci security  # run security tests and print a security score
agenci diff --baseline <run-id>   # compare against a previous run
agenci dashboard # view recent runs at http://127.0.0.1:8321
```

Point `agenci.yaml` at your real agent by changing the `agent:` block —
see [docs/adapters.md](docs/adapters.md). Agenci does not depend on any
single agent framework: it ships adapters for plain Python callables,
HTTP/REST services, OpenAI- and Anthropic-compatible chat APIs,
**LangChain/LangGraph** (`Runnable`-based, with real tool-call tracing
via callbacks), **CrewAI**, **MCP** servers, and **AutoGen** (agents
and teams, with real tool-call tracing and automatic state reset
between tests), and is architected so more can be added without
touching the core engine.

## Documentation

- [Getting started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [Writing tests](docs/tests.md)
- [Evaluations (LLM-as-judge)](docs/evaluations.md)
- [Security testing](docs/security.md)
- [Regression testing](docs/regression-testing.md)
- [Adapters](docs/adapters.md)
- [GitHub Actions](docs/github-actions.md)
- [Observability (OpenTelemetry)](docs/observability.md)
- [Architecture](docs/architecture.md)
- [Extending Agenci](docs/extending-agenci.md)

## Project status

Agenci is an early-stage, actively developed open-source project. v0.2
is complete: the CLI, evaluators, regression testing (with per-test and
per-security-category diffing), GitHub Action, OpenTelemetry export,
and GitHub PR comments are all implemented and tested. Adapters:
`python`, `http`, `openai` (v0.1), plus `langchain`, `crewai`, `mcp`,
`autogen`, `anthropic` (v0.2) — see
[docs/adapters.md](docs/adapters.md) for what's genuinely
end-to-end-verified vs. unit-tested-only for each. The security
framework covers tool authorization, required tools, a
data-exfiltration heuristic, and built-in sensitive-data pattern
scanning — see [docs/security.md](docs/security.md#categories). See
[docs/architecture.md](docs/architecture.md#roadmap)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). See [CHANGELOG.md](CHANGELOG.md)
for release history and the versioning policy.

## Security

See [SECURITY.md](SECURITY.md) for the threat model Agenci's security
framework covers (and does not cover), and how to report a vulnerability
in Agenci itself.

## License

[Apache 2.0](LICENSE)
