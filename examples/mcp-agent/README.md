# Example: mcp-agent

Demonstrates the `mcp` adapter: Agenci launches an MCP server over
stdio and calls one configured tool per test case, so you can apply
Agenci's functional/security testing directly to an MCP tool —
independent of whichever agent framework ends up calling it in
production.

## Run it

```bash
cd examples/mcp-agent
pip install 'agenci[mcp]'
agenci test
```

`agenci.yaml` sets `agent.mcp_command`/`agent.mcp_args` to launch
`server.py` itself — you don't need to start the server separately.

Verified end-to-end against `mcp==1.9.4` in a clean virtual
environment: real stdio server, real client session, real tool call,
across multiple runs. The `mcp` extra pins `mcp>=1.0,<2.0` — an
earlier, very new `2.0.0` release of the SDK exhibited a stdio
transport hang in testing; `agenci[mcp]` sticks to the well-established
1.x line until that's understood and confirmed fixed upstream.

## What to look at

- `server.py` — a real MCP server (`mcp.server.MCPServer`) exposing one
  `order_status` tool via the `@server.tool()` decorator.
- `agenci.yaml` — `agent.adapter: mcp`, `agent.mcp_command`/`mcp_args`
  (how to launch the server), `agent.mcp_tool` (which tool to call).
- `tests/basic.yaml` — each test's `input` is a JSON object, used
  directly as the tool's call arguments (see
  [../../docs/adapters.md](../../docs/adapters.md#mcp) for the other
  ways `input` can be mapped to tool arguments).
