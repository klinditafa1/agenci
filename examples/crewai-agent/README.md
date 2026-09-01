# Example: crewai-agent

Demonstrates the `crewai` adapter against a real
[CrewAI](https://docs.crewai.com/) `Crew` (one agent, one task).

Unlike `examples/langchain-agent`, this example requires a real LLM —
CrewAI agents call one internally via `litellm` — so it is **not** run
in Agenci's own CI (same reasoning as `examples/openai-agent`). The
adapter's wiring (factory resolution, `akickoff`, output/token-usage
normalization) is fully unit-tested with a duck-typed fake crew in
`tests/unit/test_crewai_adapter.py`, which *is* run in CI without
needing a real LLM.

## Run it

```bash
cd examples/crewai-agent
pip install 'agenci[crewai]'
export OPENAI_API_KEY=sk-...
agenci test
```

To use a different provider, set `AGENCI_CREWAI_MODEL` to any
[litellm-supported model string](https://docs.litellm.ai/docs/providers)
and set the matching provider's API key env var.

## What to look at

- `agent.py` — `build_crew()` is a zero-argument factory returning a
  `crewai.Crew`; Agenci calls it once per run and calls
  `crew.akickoff(inputs=...)`.
- `agenci.yaml` — `agent.adapter: crewai`, `agent.entrypoint:
  agent:build_crew`, `agent.input_key: input` (must match the
  `{input}` placeholder used in your `Task.description`).
- `tests/basic.yaml` — a functional test with an `llm_judge`
  evaluation (using the dependency-free `mock` judge provider, so you
  only need one API key — for the crew's own LLM — not two).

## Tool-call visibility

Tool calls are captured via CrewAI's own event bus
(`crewai.events.crewai_event_bus`): the adapter subscribes to
`ToolUsageFinishedEvent`/`ToolUsageErrorEvent` for the duration of
each call, so `policy:`-based tool-authorization security tests work
against a CrewAI agent the same way they do for `langchain` and
`autogen`. This is verified in
`tests/unit/test_crewai_adapter.py` against CrewAI's real event
classes (not mocked) — including a test that specifically checks tool
calls from one test case never leak into the next, since CrewAI
dispatches event handlers on a background thread pool. If your
installed CrewAI version predates this event bus, the adapter degrades
gracefully to `tool_calls: []` rather than failing. See
[../../docs/adapters.md](../../docs/adapters.md#crewai).
