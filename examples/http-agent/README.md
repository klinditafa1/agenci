# Example: http-agent

Demonstrates the `http` adapter against an agent exposed over REST,
using a minimal stdlib-only server so the example has no extra
dependencies. Any HTTP service that accepts
`POST {"input": ..., "context": ...}` and returns
`{"output": "...", ...}` works the same way — see
[../../docs/adapters.md](../../docs/adapters.md).

## Run it

```bash
cd examples/http-agent
python server.py &        # start the example agent on :8800
agenci test
kill %1                   # stop the server when done
```

## What to look at

- `server.py` — the HTTP contract Agenci's `http` adapter expects.
- `agenci.yaml` — `agent.adapter: http` pointing at `http://127.0.0.1:8800`.
- `tests/basic.yaml` — functional assertions run against the live server.
