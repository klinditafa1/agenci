# Example: langchain-agent

Demonstrates the `langchain` adapter against a real
[`Runnable`](https://python.langchain.com/docs/concepts/runnables/)
(`RunnableLambda`) that calls a LangChain `@tool` — no network, no API
key required, since it's pure Python logic wrapped in LangChain's
interfaces. The same adapter works unmodified against an LCEL chain, an
`AgentExecutor`, or a compiled LangGraph graph, since all of those are
`Runnable`s.

The key thing to notice: Agenci's security test below (`only_uses_lookup_tool`)
passes because the adapter observes the **actual tool call** made
through LangChain's callback system — not because it parsed the output
text for the word "tool".

## Run it

```bash
cd examples/langchain-agent
pip install 'agenci[langchain]'
agenci test
```

Expected: 4/4 tests pass, including the tool-authorization security check.

## What to look at

- `agent.py` — `build_chain()` is a zero-argument factory returning a
  `Runnable`; Agenci calls it once and reuses the result. A LangChain
  `@tool` (`lookup_order_status`) is invoked from inside the chain.
- `agenci.yaml` — `agent.adapter: langchain`, `agent.entrypoint:
  agent:build_chain`, `agent.input_key: input` (the variable name your
  chain expects — change this if your chain's input key differs).
- `tests/basic.yaml` — functional tests plus a `tool_authorization`
  security test, satisfied by the adapter's callback-based tool-call
  tracing (see [../../docs/adapters.md](../../docs/adapters.md)).
