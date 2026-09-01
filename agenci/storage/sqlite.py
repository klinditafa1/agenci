"""SQLite storage backend for the open-source MVP.

Schema is created with simple, idempotent ``CREATE TABLE IF NOT
EXISTS`` migrations tracked via ``PRAGMA user_version``. This keeps the
open-source project dependency-free (stdlib ``sqlite3`` only) while
still leaving room to grow into a real migration tool if/when the
schema needs more than additive changes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agenci.reporting.models import TestReport
from agenci.storage.base import RunSummary

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    created_at REAL NOT NULL,
    success_rate REAL NOT NULL,
    security_score REAL NOT NULL,
    total_tests INTEGER NOT NULL,
    total_cost_usd REAL NOT NULL,
    avg_latency_ms REAL,
    is_baseline INTEGER NOT NULL DEFAULT 0,
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_project_created
    ON runs (project, created_at DESC);
"""

DEFAULT_DB_PATH = Path(".agenci") / "agenci.db"


class SqliteStorage:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def save_run(self, report: TestReport, is_baseline: bool = False) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (
                run_id, project, created_at, success_rate, security_score,
                total_tests, total_cost_usd, avg_latency_ms, is_baseline, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                success_rate=excluded.success_rate,
                security_score=excluded.security_score,
                total_tests=excluded.total_tests,
                total_cost_usd=excluded.total_cost_usd,
                avg_latency_ms=excluded.avg_latency_ms,
                is_baseline=excluded.is_baseline,
                report_json=excluded.report_json
            """,
            (
                report.run_id,
                report.project,
                report.created_at,
                report.metrics.success_rate,
                report.metrics.security_score,
                report.metrics.total_tests,
                report.metrics.total_cost_usd,
                report.metrics.avg_latency_ms,
                int(is_baseline),
                report.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> TestReport | None:
        row = self._conn.execute("SELECT report_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return TestReport.model_validate(json.loads(row["report_json"]))

    def list_runs(self, project: str | None = None, limit: int = 20) -> list[RunSummary]:
        if project:
            rows = self._conn.execute(
                """SELECT run_id, project, created_at, success_rate, security_score,
                          total_tests, total_cost_usd, avg_latency_ms, is_baseline
                   FROM runs WHERE project = ? ORDER BY created_at DESC LIMIT ?""",
                (project, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT run_id, project, created_at, success_rate, security_score,
                          total_tests, total_cost_usd, avg_latency_ms, is_baseline
                   FROM runs ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [RunSummary(dict(row)) for row in rows]

    def latest_run(self, project: str) -> TestReport | None:
        row = self._conn.execute(
            "SELECT report_json FROM runs WHERE project = ? ORDER BY created_at DESC LIMIT 1",
            (project,),
        ).fetchone()
        if row is None:
            return None
        return TestReport.model_validate(json.loads(row["report_json"]))

    def get_baseline(self, project: str) -> TestReport | None:
        row = self._conn.execute(
            """SELECT report_json FROM runs WHERE project = ? AND is_baseline = 1
               ORDER BY created_at DESC LIMIT 1""",
            (project,),
        ).fetchone()
        if row is None:
            return None
        return TestReport.model_validate(json.loads(row["report_json"]))

    def mark_baseline(self, run_id: str) -> None:
        row = self._conn.execute("SELECT project FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"No such run: {run_id}")
        project = row["project"]
        self._conn.execute("UPDATE runs SET is_baseline = 0 WHERE project = ?", (project,))
        self._conn.execute("UPDATE runs SET is_baseline = 1 WHERE run_id = ?", (run_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def touch_gitignore(project_root: Path) -> None:
    """Ensure .agenci/ (local DB + run artifacts) is git-ignored by default."""
    gitignore = project_root / ".gitignore"
    entry = ".agenci/\n"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".agenci/" in content:
            return
        gitignore.write_text(content.rstrip("\n") + "\n" + entry)
    else:
        gitignore.write_text(f"# Agenci local run data\n{entry}")
