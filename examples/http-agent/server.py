"""A minimal HTTP agent server, using only the standard library.

Implements the contract Agenci's `http` adapter expects: POST a JSON
body `{"input": ..., "context": ...}` and respond with JSON containing
at least `{"output": "..."}`.

Run with:
    python server.py
Then, in another terminal:
    agenci test
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8800


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quiet
        pass

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        agent_input = body.get("input", "")

        output = self._handle(agent_input)

        response = json.dumps(
            {
                "output": output,
                "model": "http-agent-example-v1",
                "provider": "custom-http",
                "input_tokens": len(agent_input.split()),
                "output_tokens": len(output.split()),
            }
        ).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _handle(self, agent_input: str) -> str:
        lowered = agent_input.lower()
        if "status" in lowered and "order" in lowered:
            return "Your order is out for delivery and should arrive today."
        if "hours" in lowered:
            return "We're open Monday to Friday, 9am to 6pm."
        return "Thanks for reaching out — a support agent will follow up shortly."


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http-agent example server listening on http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
