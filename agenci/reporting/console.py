"""Human-readable (rich) and machine-readable (JSON) report rendering."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from agenci.reporting.diff import RegressionReport
from agenci.reporting.models import TestReport

console = Console()


def render_test_report(report: TestReport, *, thresholds_success: float, thresholds_security: float) -> None:
    m = report.metrics
    status = report.status(min_success_rate=thresholds_success, min_security_score=thresholds_security)
    status_style = "bold green" if status == "PASS" else "bold red"

    console.print(f"\n[bold]Agenci[/bold] — {report.project}")
    console.print(f"{m.total_tests} evaluations completed\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Suite")
    table.add_column("Passed", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Status", justify="right")

    if m.functional_total:
        f_status = "PASS" if m.functional_passed == m.functional_total else "FAIL"
        table.add_row("Functional", str(m.functional_passed), str(m.functional_total), f_status)
    if m.security_total:
        s_status = "PASS" if m.security_score >= thresholds_security * 100 else "FAIL"
        table.add_row("Security", str(m.security_passed), str(m.security_total), s_status)

    console.print(table)

    console.print(f"\nSuccess rate:   {m.success_rate * 100:.1f}%")
    console.print(f"Security score: {m.security_score:.0f}/100")
    if m.avg_latency_ms is not None:
        console.print(f"Avg latency:    {m.avg_latency_ms:.0f}ms")
    console.print(f"Estimated cost: ${m.total_cost_usd:.4f}")

    if report.security and report.security.categories:
        console.print("\n[bold]Security breakdown[/bold]")
        sec_table = Table(show_header=True, header_style="bold")
        sec_table.add_column("Category")
        sec_table.add_column("Score", justify="right")
        for cat in sorted(report.security.categories, key=lambda c: c.category):
            sec_table.add_row(cat.category.replace("_", " ").title(), f"{cat.score:.0f}")
        console.print(sec_table)

    failed = [o for o in report.outcomes if not o.passed]
    if failed:
        console.print(f"\n[bold red]{len(failed)} test(s) failed:[/bold red]")
        for o in failed:
            console.print(f"  ✗ {o.test_name}")
            for a in o.assertion_results:
                if not a.passed:
                    console.print(f"      - {a.assertion}: {a.detail}")
            for sf in o.security_findings:
                if not sf.passed:
                    console.print(f"      - [{sf.severity}] {sf.description}")
            if o.error:
                console.print(f"      - error: {o.error}")

    console.print(f"\nSTATUS: [{status_style}]{status}[/{status_style}]\n")


def render_regression_report(reg: RegressionReport) -> None:
    console.print("\n[bold]Agenci Regression Report[/bold]\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Baseline", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Delta", justify="right")

    for d in reg.deltas:
        delta_str = f"{d.delta:+.4f}"
        if d.delta_pct is not None:
            delta_str += f" ({d.delta_pct * 100:+.1f}%)"
        style = "red" if d.regressed else None
        table.add_row(
            d.name,
            f"{d.baseline:.4f}",
            f"{d.current:.4f}",
            delta_str,
            style=style,
        )
    console.print(table)

    if reg.category_deltas:
        console.print("\n[bold]Security category deltas[/bold]")
        cat_table = Table(show_header=True, header_style="bold")
        cat_table.add_column("Category")
        cat_table.add_column("Baseline", justify="right")
        cat_table.add_column("Current", justify="right")
        cat_table.add_column("Delta", justify="right")
        for d in reg.category_deltas:
            delta_str = f"{d.delta:+.1f}"
            if d.delta_pct is not None:
                delta_str += f" ({d.delta_pct * 100:+.1f}%)"
            cat_table.add_row(
                d.name.removeprefix("Security: "),
                f"{d.baseline:.0f}",
                f"{d.current:.0f}",
                delta_str,
                style="red" if d.regressed else None,
            )
        console.print(cat_table)

    if reg.newly_failing:
        console.print(f"\n[bold red]{len(reg.newly_failing)} test(s) newly failing:[/bold red]")
        for name in reg.newly_failing:
            console.print(f"  ✗ {name}")
    if reg.newly_passing:
        console.print(f"\n[bold green]{len(reg.newly_passing)} test(s) newly passing:[/bold green]")
        for name in reg.newly_passing:
            console.print(f"  ✓ {name}")
    if reg.tests_added:
        added = ", ".join(reg.tests_added)
        console.print(f"\n[dim]{len(reg.tests_added)} test(s) added since baseline:[/dim] {added}")
    if reg.tests_removed:
        removed = ", ".join(reg.tests_removed)
        console.print(f"\n[dim]{len(reg.tests_removed)} test(s) removed since baseline:[/dim] {removed}")

    status_style = "bold green" if reg.status == "PASS" else "bold red"
    console.print(f"\nSTATUS: [{status_style}]{reg.status}[/{status_style}]")
    if reg.failure_reasons:
        console.print()
        for reason in reg.failure_reasons:
            console.print(f"  - {reason}")
    console.print()


def report_to_json(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, indent=2, default=str)
