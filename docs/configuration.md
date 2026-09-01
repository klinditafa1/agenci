# Configuration reference (`agenci.yaml`)

Agenci reads `agenci.yaml` (or `agenci.yml`) from the current directory
by default, or a path passed with `--config`. Every field below is
validated with [Pydantic](https://docs.pydantic.dev/); invalid config
produces a readable error pointing at the offending field, not a
stack trace.

```yaml
project:
  name: my-agent

agent:
  adapter: python
  entrypoint: app.agent:create_agent

tests:
  directories:
    - tests

evaluation:
  judge:
    provider: openai
    model: gpt-4.1-mini

thresholds:
  success_rate: 0.90
  security_score: 0.90
  max_cost_increase: 0.20
  max_latency_increase: 0.25
  regression:
    max_drop: 0.05

cost:
  models:
    my-local-model:
      input_per_1m: 0.0
      output_per_1m: 0.0
```

## `project`

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | Also accepted as shorthand: `project: my-agent`. |
| `description` | string | none | Optional. |

## `agent`

Selects and configures the adapter Agenci uses to call your agent. See
[adapters.md](adapters.md) for the full contract of each adapter.

| Field | Type | Applies to | Notes |
|---|---|---|---|
| `adapter` | `python` \| `http` \| `openai` | all | Required. |
| `entrypoint` | string | `python` | Required for `python`. `module.path:callable_name`. |
| `url` | string | `http` | Required for `http`. |
| `headers` | map | `http` | Extra headers sent with each request. |
| `model` | string | `openai` | Required for `openai`. |
| `base_url` | string | `openai` | Defaults to `https://api.openai.com/v1`; point at any OpenAI-compatible endpoint. |
| `api_key_env` | string | `openai` | Env var holding the API key. Default `OPENAI_API_KEY`. |
| `system_prompt` | string | `openai` | Optional system message. |
| `timeout_seconds` | number | all | Default `60`. |

## `tests`

| Field | Type | Default | Notes |
|---|---|---|---|
| `directories` | list[string] | `["tests"]` | Directories scanned recursively for `*.yaml`/`*.yml` test files. |

## `evaluation.judge`

| Field | Type | Default | Notes |
|---|---|---|---|
| `provider` | `mock` \| `openai` | `mock` | `mock` needs no API key; see [evaluations.md](evaluations.md). |
| `model` | string | `gpt-4.1-mini` | Judge model, if `provider: openai`. |
| `api_key_env` | string | `OPENAI_API_KEY` | |
| `base_url` | string | none | Point at any OpenAI-compatible endpoint. |

## `thresholds`

Gates used by `agenci test` (pass/fail status) and `agenci diff`
(regression detection).

| Field | Type | Default | Meaning |
|---|---|---|---|
| `success_rate` | 0-1 | `0.90` | Minimum fraction of tests that must pass. |
| `security_score` | 0-1 | `0.90` | Minimum security score (as a fraction of 100). |
| `max_cost_increase` | number | `0.20` | Max relative cost increase before `agenci diff` fails. |
| `max_latency_increase` | number | `0.25` | Max relative latency increase before `agenci diff` fails. |
| `regression.max_drop` | 0-1 | `0.05` | Max relative drop in success rate, security score, or any individual security category before `agenci diff` fails. |
| `regression.fail_on_any_newly_failing` | bool | `false` | Fail `agenci diff` if any individual test that passed in the baseline fails now, even if the aggregate success rate stays within `max_drop`. |

## `cost.models`

Overrides/extends Agenci's built-in per-1M-token pricing table (see
[architecture.md](architecture.md#cost-tracking)). Keys are model
names as reported by your adapter; values are `input_per_1m` /
`output_per_1m` in USD. All figures are estimates.

## `execution`

| Field | Type | Default | Notes |
|---|---|---|---|
| `concurrency` | int ≥ 1 | `1` | Max test cases run concurrently. Overridable per-invocation with `--concurrency` on `agenci test`/`security`/`evaluate`. |

```yaml
execution:
  concurrency: 8
```

Automatically clamped back to `1` — with a warning printed to
stderr — for adapters that hold state concurrent calls would corrupt
(`autogen`, `crewai`; see [adapters.md](adapters.md#a-note-on-concurrency)).
For network-bound adapters (`http`, `openai`, `anthropic`) and
straightforward `python`/`langchain` agents, raising this is usually
safe and can substantially cut down wall-clock time for large suites.

## Validating configuration

```bash
agenci config validate      # human-readable OK / error
agenci config show          # fully resolved config (defaults included) as JSON
```
