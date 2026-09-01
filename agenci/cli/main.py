"""Agenci CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agenci import __version__
from agenci.adapters.registry import build_adapter
from agenci.cli import scaffold
from agenci.config.loader import ConfigError, load_config
from agenci.config.models import AgenciConfig
from agenci.core.cost import CostEstimator
from agenci.core.runner import TestRunner
from agenci.core.test_loader import TestLoadError, load_all_tests
from agenci.evaluators.engine import build_judge
from agenci.integrations.github import (
    GitHubIntegrationError,
    build_pr_comment_markdown,
    detect_pr_number,
    detect_repo,
    post_or_update_pr_comment,
)
from agenci.reporting.builder import build_report
from agenci.reporting.console import render_regression_report, render_test_report, report_to_json
from agenci.reporting.diff import RegressionReport, compare_reports
from agenci.reporting.models import TestReport
from agenci.storage.sqlite import DEFAULT_DB_PATH, SqliteStorage, touch_gitignore
from agenci.tracing.otel_export import OTelExportError, export_traces
from agenci.tracing.schema import AgentTrace

app = typer.Typer(
    name="agenci",
    help="CI/CD, evaluation, and security testing for AI agents.",
    add_completion=True,
    no_args_is_help=True,
)
config_app = typer.Typer(help="Inspect and validate agenci.yaml.")
app.add_typer(config_app, name="config")

console = Console()
err_console = Console(stderr=True)


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=code)


def _resolve_config(config_path: Path | None) -> AgenciConfig:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        _fail(str(exc))
        raise  # unreachable, satisfies type checkers


def _ensure_cwd_on_path() -> None:
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


async def _execute_suite(
    config: AgenciConfig, only_type: str | None = None, concurrency: int | None = None
) -> tuple[TestReport, list[AgentTrace]]:
    project_root = Path.cwd()
    _ensure_cwd_on_path()
    try:
        cases = load_all_tests(config.tests.directories, root=project_root)
    except TestLoadError as exc:
        _fail(str(exc))
        raise

    if only_type is not None:
        cases = [c for c in cases if c.type == only_type]
        if not cases:
            _fail(f"No test cases of type '{only_type}' found in {config.tests.directories}.")

    try:
        adapter = build_adapter(config.agent)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean CLI error, not a traceback
        _fail(f"Could not initialize agent adapter: {exc}")
        raise

    try:
        judge = build_judge(config.evaluation.judge)
    except Exception as exc:  # noqa: BLE001
        await adapter.aclose()
        _fail(f"Could not initialize judge provider: {exc}")
        raise

    resolved_concurrency = concurrency if concurrency is not None else config.execution.concurrency

    try:
        runner = TestRunner(adapter, judge=judge, cost_estimator=CostEstimator(config.cost))
        results = await runner.run_all(cases, concurrency=resolved_concurrency)
        if runner.concurrency_note:
            err_console.print(f"[yellow]Note:[/yellow] {runner.concurrency_note}")
    finally:
        await adapter.aclose()

    outcomes = [outcome for outcome, _trace in results]
    traces = [trace for _outcome, trace in results]
    return build_report(config.project.name, outcomes), traces


def _maybe_export_traces(config: AgenciConfig, traces: list[AgentTrace]) -> None:
    if not config.tracing.enabled:
        return
    try:
        export_traces(config.tracing, traces)
    except OTelExportError as exc:
        err_console.print(f"[yellow]Warning:[/yellow] OpenTelemetry export skipped: {exc}")


def _write_json_output(payload: str, output: Path | None) -> None:
    if output:
        output.write_text(payload)
        console.print(f"Wrote {output}")
    else:
        print(payload)


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Directory to initialize."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Scaffold agenci.yaml, tests/, and an example agent in PATH."""
    path.mkdir(parents=True, exist_ok=True)
    project_name = scaffold.slugify_project_name(path.resolve().name)

    files = {
        path / "agenci.yaml": scaffold.AGENCI_YAML.format(project_name=project_name),
        path / "agent.py": scaffold.EXAMPLE_AGENT_PY,
        path / "tests" / "basic.yaml": scaffold.TESTS_BASIC_YAML,
        path / "tests" / "regression.yaml": scaffold.TESTS_REGRESSION_YAML,
        path / "tests" / "security.yaml": scaffold.TESTS_SECURITY_YAML,
        path / ".github" / "workflows" / "agenci.yaml": scaffold.GITHUB_WORKFLOW_YAML,
    }

    created = []
    skipped = []
    for file_path, content in files.items():
        if file_path.exists() and not force:
            skipped.append(file_path)
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        created.append(file_path)

    touch_gitignore(path)

    for f in created:
        console.print(f"[green]created[/green]  {f}")
    for f in skipped:
        console.print(f"[yellow]skipped[/yellow]  {f} (already exists, use --force)")

    console.print("\nNext steps:")
    console.print("  agenci test")


@app.command()
def test(
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to agenci.yaml."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write JSON report to a file."),
    save_baseline: bool = typer.Option(
        False, "--save-baseline", help="Mark this run as the regression baseline."
    ),
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="Path to the local Agenci SQLite DB."),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Max test cases run concurrently. Defaults to execution.concurrency in agenci.yaml (1).",
    ),
) -> None:
    """Run functional (and security) tests against the configured agent."""
    cfg = _resolve_config(config)
    report, traces = asyncio.run(_execute_suite(cfg, concurrency=concurrency))
    _maybe_export_traces(cfg, traces)

    storage = SqliteStorage(db)
    try:
        storage.save_run(report, is_baseline=save_baseline)
    finally:
        storage.close()

    if json_output or output:
        _write_json_output(report_to_json(report), output)
    else:
        render_test_report(
            report,
            thresholds_success=cfg.thresholds.success_rate,
            thresholds_security=cfg.thresholds.security_score,
        )

    status = report.status(
        min_success_rate=cfg.thresholds.success_rate,
        min_security_score=cfg.thresholds.security_score,
    )
    raise typer.Exit(code=0 if status == "PASS" else 1)


@app.command()
def security(
    config: Path | None = typer.Option(None, "--config", "-c"),
    json_output: bool = typer.Option(False, "--json"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
    concurrency: int | None = typer.Option(None, "--concurrency"),
) -> None:
    """Run only security tests and report findings + security score."""
    cfg = _resolve_config(config)
    report, traces = asyncio.run(_execute_suite(cfg, only_type="security", concurrency=concurrency))
    _maybe_export_traces(cfg, traces)

    storage = SqliteStorage(db)
    try:
        storage.save_run(report)
    finally:
        storage.close()

    if json_output or output:
        _write_json_output(report_to_json(report), output)
    else:
        render_test_report(
            report,
            thresholds_success=cfg.thresholds.success_rate,
            thresholds_security=cfg.thresholds.security_score,
        )

    raise typer.Exit(code=0 if report.metrics.security_score >= cfg.thresholds.security_score * 100 else 1)


@app.command()
def evaluate(
    config: Path | None = typer.Option(None, "--config", "-c"),
    json_output: bool = typer.Option(False, "--json"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    concurrency: int | None = typer.Option(None, "--concurrency"),
) -> None:
    """Run the suite and report LLM-judge evaluator scores (no storage write)."""
    cfg = _resolve_config(config)
    report, traces = asyncio.run(_execute_suite(cfg, concurrency=concurrency))
    _maybe_export_traces(cfg, traces)

    if json_output or output:
        _write_json_output(report_to_json(report), output)
        return

    table = Table(title="Evaluator scores", show_header=True, header_style="bold")
    table.add_column("Test")
    table.add_column("Criterion")
    table.add_column("Score", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Result")

    any_rows = False
    for outcome in report.outcomes:
        for ev in outcome.evaluator_results:
            any_rows = True
            result = "[green]PASS[/green]" if ev.passed else "[red]FAIL[/red]"
            table.add_row(outcome.test_name, ev.criterion, f"{ev.score:.2f}", f"{ev.threshold:.2f}", result)

    if any_rows:
        console.print(table)
    else:
        console.print(
            "No test cases declare an 'evaluation:' block, so there are no "
            "LLM-judge scores to show. See docs/evaluations.md."
        )


@app.command()
def diff(
    baseline: str = typer.Option(..., "--baseline", help="Baseline run_id or path to a JSON report."),
    current: str | None = typer.Option(
        None, "--current", help="Current run_id or JSON report path (defaults to latest run)."
    ),
    config: Path | None = typer.Option(None, "--config", "-c"),
    json_output: bool = typer.Option(False, "--json"),
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
) -> None:
    """Compare a baseline run against a current run and detect regressions."""
    cfg = _resolve_config(config)
    storage = SqliteStorage(db)
    try:
        baseline_report = _load_report(baseline, storage)
        if current is not None:
            current_report = _load_report(current, storage)
        else:
            current_report = storage.latest_run(cfg.project.name)
            if current_report is None:
                _fail("No stored runs found. Run 'agenci test' first.")
    finally:
        storage.close()

    if baseline_report is None:
        _fail(f"Could not find baseline: {baseline}")
    if current_report is None:
        _fail(f"Could not find current run: {current}")

    regression = compare_reports(baseline_report, current_report, cfg.thresholds)  # type: ignore[arg-type]

    if json_output:
        print(report_to_json(regression))
    else:
        render_regression_report(regression)

    raise typer.Exit(code=0 if regression.status == "PASS" else 1)


def _load_report(ref: str, storage: SqliteStorage) -> TestReport | None:
    path = Path(ref)
    if path.suffix == ".json" and path.exists():
        return TestReport.model_validate(json.loads(path.read_text()))
    return storage.get_run(ref)


@app.command(name="pr-comment")
def pr_comment(
    report_path: Path = typer.Option(
        ..., "--report", help="Path to a JSON report from 'agenci test --json --output ...'."
    ),
    security_report_path: Path | None = typer.Option(
        None, "--security-report", help="Optional path to a JSON report from 'agenci security'."
    ),
    regression_path: Path | None = typer.Option(
        None, "--regression", help="Optional path to a JSON report from 'agenci diff --json'."
    ),
    config: Path | None = typer.Option(None, "--config", "-c"),
    repo: str | None = typer.Option(
        None, "--repo", help="'owner/name'. Defaults to agenci.yaml, then $GITHUB_REPOSITORY."
    ),
    pr: int | None = typer.Option(
        None, "--pr", help="PR number. Defaults to agenci.yaml, then auto-detection in Actions."
    ),
    token_env: str | None = typer.Option(
        None,
        "--token-env",
        help="Env var holding a GitHub token. Defaults to agenci.yaml, then GITHUB_TOKEN.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the comment markdown instead of posting it."
    ),
) -> None:
    """Post (or update) a summary comment on a GitHub pull request."""
    cfg = _resolve_config(config)

    try:
        report_obj = TestReport.model_validate(json.loads(report_path.read_text()))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"Could not read report {report_path}: {exc}")
        raise

    security_report_obj: TestReport | None = None
    if security_report_path is not None:
        try:
            security_report_obj = TestReport.model_validate(json.loads(security_report_path.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"Could not read security report {security_report_path}: {exc}")
            raise

    regression_obj: RegressionReport | None = None
    if regression_path is not None:
        try:
            regression_obj = RegressionReport.model_validate(json.loads(regression_path.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"Could not read regression report {regression_path}: {exc}")
            raise

    markdown = build_pr_comment_markdown(
        cfg.project.name,
        report_obj,
        min_success_rate=cfg.thresholds.success_rate,
        min_security_score=cfg.thresholds.security_score,
        security_report=security_report_obj,
        regression=regression_obj,
    )

    if dry_run:
        print(markdown)
        return

    resolved_repo = repo or cfg.github.repo or detect_repo()
    resolved_pr = pr or cfg.github.pr_number or detect_pr_number()
    resolved_token_env = token_env or cfg.github.token_env
    token = os.environ.get(resolved_token_env)

    if not resolved_repo:
        _fail("Could not determine the repository. Pass --repo owner/name or set GITHUB_REPOSITORY.")
    if resolved_repo and not re.fullmatch(r"[\w.-]+/[\w.-]+", resolved_repo):
        _fail(f"'{resolved_repo}' doesn't look like a valid 'owner/name' repository.")
    if not resolved_pr:
        _fail(
            "Could not determine the pull request number. Pass --pr or run inside a "
            "GitHub Actions pull_request job."
        )
    if not token:
        _fail(f"No GitHub token found in ${resolved_token_env}. Pass --token-env or set the variable.")

    try:
        result = asyncio.run(
            post_or_update_pr_comment(
                markdown,
                project=cfg.project.name,
                repo=resolved_repo,  # type: ignore[arg-type]
                pr_number=resolved_pr,  # type: ignore[arg-type]
                token=token,  # type: ignore[arg-type]
            )
        )
    except GitHubIntegrationError as exc:
        _fail(str(exc))
        raise

    console.print(f"Posted PR comment: {result.get('html_url', result.get('id'))}")


@app.command()
def report(
    run_id: str | None = typer.Option(None, "--run-id", help="Specific run to show."),
    project: str | None = typer.Option(None, "--project", help="Filter by project name."),
    json_output: bool = typer.Option(False, "--json"),
    limit: int = typer.Option(10, "--limit"),
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
) -> None:
    """Show a stored run report, or list recent runs."""
    storage = SqliteStorage(db)
    try:
        if run_id:
            found = storage.get_run(run_id)
            if found is None:
                _fail(f"No such run: {run_id}")
            if json_output:
                print(report_to_json(found))
            else:
                render_test_report(found, thresholds_success=0.9, thresholds_security=0.9)  # type: ignore[union-attr]
            return

        runs = storage.list_runs(project=project, limit=limit)
        if json_output:
            print(json.dumps(runs, indent=2, default=str))
            return
        if not runs:
            console.print("No runs recorded yet. Run 'agenci test' first.")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Run ID")
        table.add_column("Project")
        table.add_column("Success")
        table.add_column("Security")
        table.add_column("Tests", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Baseline")
        for run in runs:
            table.add_row(
                run["run_id"][:12],
                run["project"],
                f"{run['success_rate'] * 100:.1f}%",
                f"{run['security_score']:.0f}",
                str(run["total_tests"]),
                f"${run['total_cost_usd']:.4f}",
                "✓" if run["is_baseline"] else "",
            )
        console.print(table)
    finally:
        storage.close()


@app.command()
def dashboard(
    port: int = typer.Option(8321, "--port", "-p"),
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
) -> None:
    """Serve a simple local dashboard of recent runs."""
    from agenci.dashboard.server import serve

    serve(db_path=db, port=port)


@config_app.command("validate")
def config_validate(
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Validate agenci.yaml and print a human-readable error if invalid."""
    cfg = _resolve_config(config)
    console.print(f"[green]OK[/green] — configuration for project '{cfg.project.name}' is valid.")


@config_app.command("show")
def config_show(
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Print the fully resolved configuration (defaults included) as JSON."""
    cfg = _resolve_config(config)
    print(report_to_json(cfg))


@app.command()
def version() -> None:
    """Print the installed Agenci version."""
    console.print(f"agenci {__version__}")


def _entrypoint() -> None:
    try:
        app()
    except ConfigError as exc:  # safety net if not caught earlier
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    _entrypoint()
