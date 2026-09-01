# Adapters

Agenci never talks to an agent framework directly — it only ever calls
`AgentAdapter.run(input, context)`. This is the seam that keeps Agenci
framework-neutral: every feature (assertions, evaluation, security,
tracing, cost tracking) is written against the normalized
`AgentResponse`, not against LangChain, CrewAI, or any other SDK.

```python
class AgentAdapter(Protocol):
    async def run(self, input: str, context: dict | None = None) -> AgentResponse: ...
    async def aclose(self) -> None: ...

class AgentResponse(BaseModel):
    output: str
    tool_calls: list[ToolCallRecord] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    provider: str | None = None
    error: str | None = None
```

## Built-in adapters

### `python`

Calls a local Python callable directly, in-process. Works with any
callable of the shape `fn(input: str, context: dict) -> str | dict`,
so it covers hand-rolled agents as well as thin wrappers around
LangChain, LangGraph, CrewAI, AutoGen, etc. without Agenci depending on
any of those packages.

```yaml
agent:
  adapter: python
  entrypoint: app.agent:create_agent   # module.path:callable_name
```

The return value can be:

- a `str` — used as `output` directly.
- a `dict` — `{"output": ..., "tool_calls": [...], "input_tokens": ..., "output_tokens": ..., "model": ..., "provider": ...}`. Only `output` is required.
- an `AgentResponse` — used as-is.

`entrypoint` can also point at a **zero-argument factory**: if the
resolved callable takes no arguments, Agenci calls it once and looks
for a `.run()` or `.invoke()` method (or treats the result itself as
callable) — this covers the common `create_agent() -> Agent` pattern.

Both sync and `async def` callables are supported.

### `http`

Calls an agent exposed over HTTP/REST.

```yaml
agent:
  adapter: http
  url: https://my-agent.example.com/run
  headers:
    Authorization: "Bearer ${AGENT_API_KEY}"
```

Agenci `POST`s `{"input": ..., "context": ...}` and expects:

```json
{
  "output": "...",
  "tool_calls": [{"tool": "search", "arguments": {}, "result": null}],
  "input_tokens": 123,
  "output_tokens": 45,
  "model": "...",
  "provider": "..."
}
```

Only `output` is required; everything else enriches traces, cost
tracking, and security checks when present. See
[examples/http-agent](../examples/http-agent) for a minimal reference
server.

### `openai`

Calls an OpenAI-compatible `/chat/completions` endpoint directly with
`httpx` (no `openai` package dependency), so it works unmodified
against self-hosted vLLM/Ollama gateways, OpenRouter, or any other
OpenAI-compatible route by changing `base_url`.

```yaml
agent:
  adapter: openai
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
  base_url: null            # defaults to https://api.openai.com/v1
  system_prompt: "You are a helpful support agent."
```

### `anthropic`

Calls the Anthropic Messages API (`/v1/messages`) directly with
`httpx` (no `anthropic` package dependency) — the same "no vendor SDK"
approach as the `openai` adapter, so it works unmodified against any
Anthropic-compatible `base_url` (a proxy or gateway implementing the
same Messages API shape).

```yaml
agent:
  adapter: anthropic
  model: claude-sonnet-5
  api_key_env: ANTHROPIC_API_KEY   # auto-set if you don't set it
  base_url: null                     # defaults to https://api.anthropic.com
  system_prompt: "You are a helpful support agent."
  max_tokens: 1024                   # required by the Messages API
```

`api_key_env` defaults to `OPENAI_API_KEY` at the schema level (it's a
field shared across every model-calling adapter) — Agenci detects that
you left it at that default when `adapter: anthropic` and switches it
to `ANTHROPIC_API_KEY` automatically, so you don't need to repeat it.
Set `api_key_env` explicitly if your key lives in a different variable.

Multi-block text responses are concatenated in order; token usage
comes from the response's `usage.input_tokens`/`usage.output_tokens`.

### `langchain`

Calls a [LangChain](https://python.langchain.com/) `Runnable` — an LCEL
chain, an `AgentExecutor`, or a compiled **LangGraph** graph, since all
three implement the same `Runnable` interface. Only `langchain-core` is
required (`pip install 'agenci[langchain]'`), not the full `langchain`
metapackage.

```yaml
agent:
  adapter: langchain
  entrypoint: app.agent:build_chain   # module.path:callable_name
  input_key: input                    # variable name your chain expects
```

`entrypoint` resolves to either a `Runnable` directly, or a
zero-argument factory that builds and returns one (the common
`build_chain()` / `create_agent()` pattern). Agenci calls
`.ainvoke()` (or `.invoke()` if async isn't available) with
`{input_key: input, **context}`.

**Tool-call and token-usage tracing is real, not inferred**: a
`langchain_core.callbacks.BaseCallbackHandler` is attached to every
invocation and records `on_tool_start`/`on_tool_end`/`on_llm_end`
events, so `policy:`-based security tests
(see [security.md](security.md)) work against actual tool
invocations your chain made — see
[examples/langchain-agent](../examples/langchain-agent) for a
verified, runnable example including a passing `tool_authorization`
test.

Output extraction: a `str` result is used directly; a `BaseMessage`
uses `.content`; a `dict` checks `output_key` (if set), then
`output`/`answer`/`result`/`text` in order, then falls back to
`str()` of the whole response.

### `crewai`

Calls a [CrewAI](https://docs.crewai.com/) `Crew`. Requires the
`crewai` package (`pip install 'agenci[crewai]'`) and, at runtime, a
real LLM — CrewAI agents call one internally via `litellm`.

```yaml
agent:
  adapter: crewai
  entrypoint: app.agent:build_crew   # module.path:callable_name
  input_key: input                    # matches {input} in your Task description
```

`entrypoint` resolves to a zero-argument factory returning a `Crew`.
Agenci calls `crew.akickoff(inputs={input_key: input, **context})` (or
`kickoff_async()`/a threaded `kickoff()` on older CrewAI versions) and
normalizes `CrewOutput.raw` as the output, `CrewOutput.token_usage` as
token counts.

**Tool-call and token-usage tracing is real**: tool calls are captured
via CrewAI's own event bus (`crewai.events.crewai_event_bus`) —
the adapter subscribes to
`ToolUsageFinishedEvent`/`ToolUsageErrorEvent` for the duration of
each call and unsubscribes immediately after, so `policy:`-based
tool-authorization tests work against real tool invocations, the same
guarantee the `langchain` and `autogen` adapters provide. Because
CrewAI dispatches these events on a background thread pool rather than
inline, the adapter calls the event bus's `flush()` before reading
collected tool calls, to avoid a race where a call's own events are
still in flight when it returns; this is specifically covered by
`tests/unit/test_crewai_adapter.py`, including a test that two
back-to-back runs never see each other's tool calls. If your installed
CrewAI version predates this event bus, the adapter degrades
gracefully to `tool_calls: []` rather than failing. See
[examples/crewai-agent](../examples/crewai-agent).

### `mcp`

Connects to an [MCP](https://modelcontextprotocol.io/) server as a
client and calls one configured tool per test case — useful for
testing an MCP server/tool directly, independent of whichever
LLM/agent framework calls it in production. Requires the `mcp` package
(`pip install 'agenci[mcp]'`).

```yaml
agent:
  adapter: mcp
  mcp_command: python3           # command used to launch the server
  mcp_args: ["server.py"]        # arguments to mcp_command
  mcp_tool: order_status         # tool to call on every test case
```

How a test case's `input` becomes the tool's call arguments:

1. If `context.mcp_arguments` is a mapping, it's used as-is.
2. Else if `input` parses as a JSON object, that object is used
   directly — e.g. `input: '{"order_id": "1001"}'`.
3. Otherwise, `input` is passed as a single string argument:
   `{"input": input}`.

See [examples/mcp-agent](../examples/mcp-agent) for a runnable server
+ config, verified end-to-end (real stdio server, real client session,
real tool call) against `mcp==1.9.4`. The `mcp` extra pins
`mcp>=1.0,<2.0` — an early `2.0.0` SDK release exhibited a stdio
transport hang in testing, so `agenci[mcp]` sticks to the
well-established 1.x line for now.

### `autogen`

Calls an [AutoGen](https://microsoft.github.io/autogen/) (`autogen-agentchat`)
agent or team. Requires `autogen-agentchat`/`autogen-core`
(`pip install 'agenci[autogen]'`).

```yaml
agent:
  adapter: autogen
  entrypoint: app.agent:build_agent   # module.path:callable_name
```

`entrypoint` resolves to a zero-argument factory returning anything
implementing AutoGen's `TaskRunner` interface — an `AssistantAgent`, or
a multi-agent `Team` (`RoundRobinGroupChat`, `SelectorGroupChat`, ...).
Both expose the same `async def run(*, task: str) -> TaskResult`, so
this one adapter covers single agents and teams uniformly. Agenci
calls `runner.run(task=input)` and normalizes the result.

**Tool-call and token-usage tracing is real**: tool calls are parsed
from the actual `ToolCallRequestEvent`/`ToolCallExecutionEvent`
messages AutoGen emits during a run, and token usage is summed from
each message's `models_usage` — so `policy:`-based security tests work
against real tool invocations, the same guarantee the `langchain`
adapter provides. See [examples/autogen-agent](../examples/autogen-agent)
for a verified, runnable example (using AutoGen's own
`ReplayChatCompletionClient` so it needs no network access or API key)
including a passing `tool_authorization` test.

**State isolation between test cases**: an `AssistantAgent`/`Team`
built once by the factory keeps conversation state across calls by
default. This adapter resets it (`.reset()` for a `Team`, `.on_reset()`
for an `AssistantAgent` — whichever the runner exposes) before every
test case, so one test's conversation never leaks into the next. This
is verified directly in `tests/unit/test_autogen_adapter.py`.

## A note on concurrency

`agenci test --concurrency N` (or `execution.concurrency` in
`agenci.yaml`) runs up to `N` test cases at once, which can
significantly cut down wall-clock time for large suites against
network-bound adapters (`http`, `openai`, `anthropic`) — each request
is independent, so `httpx.AsyncClient` handles concurrent calls safely.
`python` and `langchain` are generally safe too, as long as your own
agent/chain doesn't hold mutable cross-call state (e.g. a shared
conversation-memory object your code writes to).

`autogen` and `crewai` are automatically clamped to `concurrency: 1`
regardless of what you configure, because both hold state that
concurrent calls would corrupt:

- **`autogen`**: the adapter reuses one `AssistantAgent`/`Team`
  instance across test cases and resets its conversation history in
  place between calls (see [above](#autogen)) — two concurrent calls
  would race on that reset and each other's conversation state.
- **`crewai`**: the adapter subscribes to CrewAI's process-global
  event bus per call to capture tool calls (see [above](#crewai)) —
  two concurrent calls would each see the other's tool-usage events.

This clamp is automatic and prints a note to stderr; it isn't
something you need to configure around. Results are always returned in
the same order as your test files define them, regardless of
completion order or concurrency level — see
`tests/unit/test_runner.py` for the tests covering this (including a
deliberately reversed-completion-order case).

## Planned adapters

None currently open — all adapters listed in the v0.2 milestone
(see [architecture.md](architecture.md#roadmap)) are implemented.
Agenci does not claim an integration works until it does — see
[Extending Agenci](extending-agenci.md#adding-an-adapter) if you'd
like to build a new one; the whole surface area is implementing
`AgentAdapter` and adding one branch to `agenci/adapters/registry.py`.
