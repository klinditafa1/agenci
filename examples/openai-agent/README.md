# Example: openai-agent

Demonstrates the `openai` adapter, which calls an OpenAI-compatible
chat completions API directly (no `openai` package dependency), plus
the `openai` judge provider for real LLM-as-judge evaluation.

This example requires a real API key and network access, so it is
**not** run in Agenci's own CI — the other examples (`basic-agent`,
`http-agent`, `security-testing`, `regression-testing`) demonstrate the
same features without any external dependency.

## Run it

```bash
cd examples/openai-agent
export OPENAI_API_KEY=sk-...
agenci test
```

To point at a different OpenAI-compatible endpoint (self-hosted vLLM,
OpenRouter, Azure OpenAI-compatible routes, etc.), set `agent.base_url`
in `agenci.yaml`.

## What to look at

- `agenci.yaml` — `agent.adapter: openai`, `agent.model`, and
  `agent.system_prompt`; `evaluation.judge.provider: openai` for real
  LLM-as-judge scoring instead of the built-in `mock` provider.
- `tests/basic.yaml` — a functional + `llm_judge` test and a
  prompt-injection resistance test.
