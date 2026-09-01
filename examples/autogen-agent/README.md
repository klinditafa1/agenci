# Example: autogen-agent

Demonstrates the `autogen` adapter against a real
[AutoGen](https://microsoft.github.io/autogen/) `AssistantAgent` with
a real tool, using AutoGen's own `ReplayChatCompletionClient` in place
of a live LLM — no network access or API key required. The same
adapter works unmodified against a multi-agent `Team` (e.g.
`RoundRobinGroupChat`, `SelectorGroupChat`), since both share AutoGen's
`run(task=...)` interface.

The key thing to notice: Agenci's security test below
(`only_uses_lookup_tool`) passes because the adapter observes the
**actual tool call** AutoGen made — via the real
`ToolCallRequestEvent`/`ToolCallExecutionEvent` messages — not because
it parsed the output text.

## A note on the scripted model

`agent.py`'s `build_agent()` wires up `ReplayChatCompletionClient` with
one pre-scripted tool call per test case, matched **by position** to
`tests/basic.yaml`. This means the example proves the adapter's
plumbing is correct (factory resolution, real tool-call tracing, token
usage, and — critically — that conversation state is reset between
test cases so test 2 never sees test 1's history) without needing a
real model call. It does **not** prove your prompt makes a real LLM
choose the right tool; that needs a real model client
(`OpenAIChatCompletionClient`, etc.) and, ideally, an `llm_judge`
evaluation — swap `ReplayChatCompletionClient` for a real one and this
same test suite becomes a real regression check.

## Run it

```bash
cd examples/autogen-agent
pip install 'agenci[autogen]'
agenci test
```

Expected: 3/3 tests pass (2 functional + 1 security), including the
tool-authorization check.

## What to look at

- `agent.py` — `build_agent()` is a zero-argument factory returning an
  `AssistantAgent`; Agenci calls it once and resets its state before
  every test case.
- `agenci.yaml` — `agent.adapter: autogen`, `agent.entrypoint:
  agent:build_agent`.
- `tests/basic.yaml` — functional tests plus a `tool_authorization`
  security test, satisfied by the adapter's real tool-call tracing
  (see [../../docs/adapters.md](../../docs/adapters.md#autogen)).
