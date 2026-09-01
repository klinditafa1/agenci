# Example: anthropic-agent

Demonstrates the `anthropic` adapter, which calls the Anthropic
Messages API directly (no `anthropic` package dependency), the same
"no vendor SDK" approach as the `openai` adapter.

This example requires a real API key and network access, so it is
**not** run in Agenci's own CI — the adapter itself is fully
unit-tested against a mocked Messages API in
`tests/unit/test_anthropic_adapter.py`, which *is* run in CI. See
`examples/langchain-agent` or `examples/autogen-agent` if you want a
fully offline, CI-verified example to start from instead.

## Run it

```bash
cd examples/anthropic-agent
export ANTHROPIC_API_KEY=sk-ant-...
agenci test
```

To point at a different Messages-API-compatible endpoint (a proxy or
gateway), set `agent.base_url` in `agenci.yaml`.

## What to look at

- `agenci.yaml` — `agent.adapter: anthropic`, `agent.model`,
  `agent.system_prompt`, `agent.max_tokens` (required by the Messages
  API). `agent.api_key_env` isn't set explicitly — it defaults to
  `ANTHROPIC_API_KEY` automatically for this adapter.
- `tests/basic.yaml` — a functional + `llm_judge` test (using the
  dependency-free `mock` judge provider, so you only need the one API
  key for the agent itself) and a prompt-injection resistance test.
