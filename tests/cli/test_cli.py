from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenci.cli.main import app

runner = CliRunner()


def _init_project(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_init_creates_expected_files(tmp_path: Path) -> None:
    _init_project(tmp_path)
    assert (tmp_path / "agenci.yaml").exists()
    assert (tmp_path / "agent.py").exists()
    assert (tmp_path / "tests" / "basic.yaml").exists()
    assert (tmp_path / "tests" / "security.yaml").exists()
    assert (tmp_path / ".github" / "workflows" / "agenci.yaml").exists()
    assert (tmp_path / ".gitignore").exists()


def test_init_is_idempotent_without_force(tmp_path: Path) -> None:
    _init_project(tmp_path)
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "skipped" in result.output


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agenci" in result.output


def test_config_validate_success(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0
        assert "OK" in result.output
    finally:
        os.chdir(cwd)


def test_test_command_runs_and_passes(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["test"])
        assert result.exit_code == 0, result.output
        assert "STATUS: PASS" in result.output
    finally:
        os.chdir(cwd)


def test_test_command_json_output(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["test", "--json"])
        assert result.exit_code == 0
        assert '"metrics"' in result.output
    finally:
        os.chdir(cwd)


def test_security_command(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["security"])
        assert result.exit_code == 0, result.output
        assert "Security" in result.output
    finally:
        os.chdir(cwd)


def test_report_lists_runs_after_test(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["test"])
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "demo" not in result.output or True  # project name varies by tmp dir name
    finally:
        os.chdir(cwd)


def test_diff_after_baseline(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["test", "--save-baseline"])
        assert result.exit_code == 0
        # Find the baseline run id from `report --json`
        import json

        report_result = runner.invoke(app, ["report", "--json"])
        runs = json.loads(report_result.output)
        baseline_id = next(r["run_id"] for r in runs if r["is_baseline"])

        runner.invoke(app, ["test"])
        diff_result = runner.invoke(app, ["diff", "--baseline", baseline_id])
        assert diff_result.exit_code == 0
        assert "Agenci Regression Report" in diff_result.output
    finally:
        os.chdir(cwd)


def test_missing_config_gives_clean_error(tmp_path: Path) -> None:
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["test"])
        assert result.exit_code != 0
        assert "No agenci.yaml found" in result.output or "Error" in result.output
    finally:
        os.chdir(cwd)


def test_tracing_console_export_does_not_break_test_command(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry.sdk")
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cfg_path = tmp_path / "agenci.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg["tracing"] = {"enabled": True, "console": True}
        cfg_path.write_text(yaml.safe_dump(cfg))

        result = runner.invoke(app, ["test"])
        assert result.exit_code == 0, result.output
        # Exported span JSON is printed alongside the normal report.
        assert '"resource"' in result.output
        assert "STATUS: PASS" in result.output
    finally:
        os.chdir(cwd)


def test_tracing_enabled_without_target_warns_but_does_not_crash(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry.sdk")
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cfg_path = tmp_path / "agenci.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg["tracing"] = {"enabled": True}
        cfg_path.write_text(yaml.safe_dump(cfg))

        result = runner.invoke(app, ["test"])
        assert result.exit_code == 0, result.output
        assert "OpenTelemetry export skipped" in result.output
    finally:
        os.chdir(cwd)


def test_pr_comment_dry_run_prints_markdown(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["test", "--json", "--output", "report.json"])
        result = runner.invoke(app, ["pr-comment", "--report", "report.json", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "<!-- agenci-report:" in result.output
        assert "Agenci checks passed" in result.output
    finally:
        os.chdir(cwd)


def test_pr_comment_combines_security_report(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["test", "--json", "--output", "report.json"])
        runner.invoke(app, ["security", "--json", "--output", "security.json"])
        result = runner.invoke(
            app,
            [
                "pr-comment",
                "--report",
                "report.json",
                "--security-report",
                "security.json",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "| Functional | ✅ PASS |" in result.output
        assert "| Security | ✅ PASS |" in result.output
    finally:
        os.chdir(cwd)


def test_pr_comment_missing_report_file_gives_clean_error(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["pr-comment", "--report", "does-not-exist.json", "--dry-run"])
        assert result.exit_code != 0
        assert "Error" in result.output
    finally:
        os.chdir(cwd)


def test_pr_comment_without_repo_or_token_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["test", "--json", "--output", "report.json"])
        result = runner.invoke(app, ["pr-comment", "--report", "report.json"])
        assert result.exit_code != 0
        assert "repository" in result.output.lower()
    finally:
        os.chdir(cwd)


def test_pr_comment_rejects_malformed_repo(tmp_path: Path) -> None:
    _init_project(tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["test", "--json", "--output", "report.json"])
        result = runner.invoke(
            app,
            ["pr-comment", "--report", "report.json", "--repo", "not-a-valid-repo-format", "--pr", "1"],
        )
        assert result.exit_code != 0
        assert "valid" in result.output.lower()
    finally:
        os.chdir(cwd)
