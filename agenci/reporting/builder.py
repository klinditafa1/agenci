from __future__ import annotations

from agenci.core.models import TestOutcome
from agenci.reporting.models import Metrics, TestReport
from agenci.security.scoring import compute_security_score


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[idx]


def build_report(project: str, outcomes: list[TestOutcome]) -> TestReport:
    total = len(outcomes)
    passed = sum(1 for o in outcomes if o.passed)

    functional = [o for o in outcomes if o.test_type == "functional"]
    security = [o for o in outcomes if o.test_type == "security"]

    latencies = [o.latency_ms for o in outcomes if o.latency_ms is not None]
    security_report = compute_security_score(outcomes) if security else None

    metrics = Metrics(
        total_tests=total,
        passed_tests=passed,
        failed_tests=total - passed,
        success_rate=round(passed / total, 4) if total else 1.0,
        functional_total=len(functional),
        functional_passed=sum(1 for o in functional if o.passed),
        security_total=len(security),
        security_passed=sum(1 for o in security if o.passed),
        security_score=security_report.overall_score if security_report else 100.0,
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else None,
        p95_latency_ms=round(p, 1) if (p := _percentile(latencies, 0.95)) is not None else None,
        total_cost_usd=round(sum(o.estimated_cost_usd for o in outcomes), 6),
        total_input_tokens=sum(o.input_tokens for o in outcomes),
        total_output_tokens=sum(o.output_tokens for o in outcomes),
    )

    return TestReport(project=project, metrics=metrics, outcomes=outcomes, security=security_report)
