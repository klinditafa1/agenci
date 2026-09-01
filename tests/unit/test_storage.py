from __future__ import annotations

from pathlib import Path

from agenci.core.models import TestOutcome
from agenci.reporting.builder import build_report
from agenci.storage.sqlite import SqliteStorage


def _report(project: str = "proj"):
    outcomes = [
        TestOutcome(test_name="a", test_type="functional", passed=True, input="i", output="o"),
    ]
    return build_report(project, outcomes)


def test_save_and_get_run(tmp_path: Path) -> None:
    storage = SqliteStorage(tmp_path / "test.db")
    try:
        report = _report()
        storage.save_run(report)
        fetched = storage.get_run(report.run_id)
        assert fetched is not None
        assert fetched.project == "proj"
        assert fetched.metrics.total_tests == 1
    finally:
        storage.close()


def test_list_runs_ordered_desc(tmp_path: Path) -> None:
    storage = SqliteStorage(tmp_path / "test.db")
    try:
        r1 = _report()
        r2 = _report()
        r2.created_at = r1.created_at + 10
        storage.save_run(r1)
        storage.save_run(r2)
        runs = storage.list_runs(project="proj")
        assert runs[0]["run_id"] == r2.run_id
    finally:
        storage.close()


def test_baseline_marking(tmp_path: Path) -> None:
    storage = SqliteStorage(tmp_path / "test.db")
    try:
        r1 = _report()
        r2 = _report()
        storage.save_run(r1)
        storage.save_run(r2)
        storage.mark_baseline(r1.run_id)
        baseline = storage.get_baseline("proj")
        assert baseline is not None
        assert baseline.run_id == r1.run_id

        storage.mark_baseline(r2.run_id)
        baseline2 = storage.get_baseline("proj")
        assert baseline2.run_id == r2.run_id
    finally:
        storage.close()


def test_get_missing_run_returns_none(tmp_path: Path) -> None:
    storage = SqliteStorage(tmp_path / "test.db")
    try:
        assert storage.get_run("does-not-exist") is None
    finally:
        storage.close()
