"""Storage backend interface.

The open-source MVP ships a SQLite implementation. The interface is
kept intentionally narrow and provider-neutral so the future hosted
platform can implement the same protocol against PostgreSQL without
changing any calling code (CLI, dashboard, GitHub Action).
"""

from __future__ import annotations

from typing import Protocol

from agenci.reporting.models import TestReport


class RunSummary(dict):
    """Lightweight dict-shaped summary used for listing runs (dashboard, CLI)."""


class StorageBackend(Protocol):
    def save_run(self, report: TestReport) -> None: ...

    def get_run(self, run_id: str) -> TestReport | None: ...

    def list_runs(self, project: str | None = None, limit: int = 20) -> list[RunSummary]: ...

    def latest_run(self, project: str) -> TestReport | None: ...

    def close(self) -> None: ...
