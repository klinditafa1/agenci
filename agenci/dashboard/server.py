"""A deliberately simple local dashboard.

Per the spec: the CLI is the primary interface, and the dashboard
should not absorb most of the development effort. This uses only the
Python standard library (``http.server``) so ``agenci dashboard`` works
with zero extra dependencies. It reads directly from the SQLite
storage backend on every request — no separate build step, no
JavaScript framework, no bundler.
"""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agenci.storage.sqlite import SqliteStorage

_PAGE_TEMPLATE = """\
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Agenci Dashboard</title>
  <style>
    body {{
      font-family: -apple-system, Segoe UI, sans-serif;
      margin: 2rem; background: #0b0d10; color: #e6e6e6;
    }}
    h1 {{ font-size: 1.4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #2a2e33; }}
    th {{ color: #9aa4af; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
    tr:hover {{ background: #14171b; }}
    .pass {{ color: #4ade80; }}
    .fail {{ color: #f87171; }}
    .baseline {{ color: #60a5fa; }}
    a {{ color: #93c5fd; text-decoration: none; }}
    .muted {{ color: #9aa4af; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>Agenci Dashboard</h1>
  <p class="muted">Local view of recent runs. Refresh to see new results.</p>
  {content}
</body>
</html>
"""


def _runs_table_html(runs: Sequence[dict]) -> str:
    if not runs:
        return "<p>No runs recorded yet. Run <code>agenci test</code> first.</p>"
    rows = []
    for run in runs:
        status_class = "pass" if run["success_rate"] >= 0.9 else "fail"
        baseline = '<span class="baseline">baseline</span>' if run["is_baseline"] else ""
        latency_cell = f"<td>{run['avg_latency_ms']:.0f}ms</td>" if run["avg_latency_ms"] else "<td>-</td>"
        rows.append(
            "<tr>"
            f'<td><a href="/run?id={html.escape(run["run_id"])}">{html.escape(run["run_id"][:12])}</a></td>'
            f"<td>{html.escape(run['project'])}</td>"
            f'<td class="{status_class}">{run["success_rate"] * 100:.1f}%</td>'
            f"<td>{run['security_score']:.0f}</td>"
            f"<td>{run['total_tests']}</td>"
            f"<td>${run['total_cost_usd']:.4f}</td>"
            f"{latency_cell}"
            f"<td>{baseline}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Run</th><th>Project</th><th>Success</th><th>Security</th>"
        "<th>Tests</th><th>Cost</th><th>Latency</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _run_detail_html(report_json: str) -> str:
    data = json.loads(report_json)
    outcomes = data.get("outcomes", [])
    rows = []
    for o in outcomes:
        status_class = "pass" if o["passed"] else "fail"
        rows.append(
            f'<tr><td class="{status_class}">{"PASS" if o["passed"] else "FAIL"}</td>'
            f"<td>{html.escape(o['test_name'])}</td><td>{html.escape(o['test_type'])}</td>"
            f"<td>{o.get('latency_ms') or '-'}</td></tr>"
        )
    table = (
        "<table><thead><tr><th>Status</th><th>Test</th><th>Type</th><th>Latency (ms)</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )
    return f'<p><a href="/">&larr; back</a></p><h2>{html.escape(data["project"])}</h2>{table}'


def _make_handler(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # quiet by default
            pass

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlparse(self.path)
            storage = SqliteStorage(db_path)
            try:
                if parsed.path == "/run":
                    run_id = parse_qs(parsed.query).get("id", [None])[0]
                    report = storage.get_run(run_id) if run_id else None
                    if report is None:
                        content = "<p>Run not found.</p>"
                    else:
                        content = _run_detail_html(report.model_dump_json())
                elif parsed.path == "/api/runs":
                    runs = storage.list_runs(limit=50)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(runs, default=str).encode())
                    return
                else:
                    runs = storage.list_runs(limit=50)
                    content = _runs_table_html(runs)
            finally:
                storage.close()

            body = _PAGE_TEMPLATE.format(content=content).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(db_path: Path, port: int = 8321) -> None:
    handler = _make_handler(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Agenci dashboard running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
