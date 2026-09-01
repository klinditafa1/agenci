# Example: basic-agent

The smallest possible Agenci setup: a plain Python function agent
(`agent.py`) tested with the `python` adapter and functional
assertions, plus one `llm_judge` evaluation using the built-in `mock`
judge provider (no API key required).

## Run it

```bash
cd examples/basic-agent
agenci test
```

Expected output: 4/4 functional tests pass.

## What to look at

- `agent.py` — the agent under test. Any callable of the shape
  `fn(input: str, context: dict) -> str` works with the `python`
  adapter; see [../../docs/adapters.md](../../docs/adapters.md).
- `agenci.yaml` — points `agent.entrypoint` at `agent:run_agent`.
- `tests/basic.yaml` — functional assertions (`contains`,
  `not_contains`) and one LLM-judge evaluation.
