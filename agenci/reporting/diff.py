"""Compares a baseline TestReport against a current TestReport.

This is the core of Agenci's regression-testing feature (section 7 of
the spec): detect and explain drops in success rate, security score,
and cost/latency increases beyond configured thresholds — plus, for
more actionable analytics than aggregate metrics alone give you,
exactly *which* tests and *which* security categories regressed.
"""

from __future__ import annotations

from pydantic import BaseModel

from agenci.config.models import ThresholdsConfig
from agenci.reporting.models import TestReport


class MetricDelta(BaseModel):
    name: str
    baseline: float
    current: float
    delta: float
    delta_pct: float | None
    regressed: bool
    reason: str = ""


class RegressionReport(BaseModel):
    status: str  # "PASS" | "FAIL"
    deltas: list[MetricDelta]
    failure_reasons: list[str]

    # Per-test analytics: exactly which tests changed status, not just
    # the aggregate success rate.
    newly_failing: list[str] = []
    newly_passing: list[str] = []
    tests_added: list[str] = []
    tests_removed: list[str] = []

    # Per-security-category analytics: catches a category regressing
    # even when the overall security score stays within tolerance
    # because another category improved.
    category_deltas: list[MetricDelta] = []


def _delta_pct(baseline: float, current: float) -> float | None:
    if baseline == 0:
        return None
    return (current - baseline) / baseline


def _diff_test_outcomes(
    baseline: TestReport, current: TestReport
) -> tuple[list[str], list[str], list[str], list[str]]:
    baseline_status = {o.test_name: o.passed for o in baseline.outcomes}
    current_status = {o.test_name: o.passed for o in current.outcomes}

    common = set(baseline_status) & set(current_status)
    newly_failing = sorted(name for name in common if baseline_status[name] and not current_status[name])
    newly_passing = sorted(name for name in common if not baseline_status[name] and current_status[name])
    tests_added = sorted(set(current_status) - set(baseline_status))
    tests_removed = sorted(set(baseline_status) - set(current_status))
    return newly_failing, newly_passing, tests_added, tests_removed


def _diff_security_categories(
    baseline: TestReport, current: TestReport, max_relative_drop: float
) -> list[MetricDelta]:
    if baseline.security is None or current.security is None:
        return []

    baseline_scores = {c.category: c.score for c in baseline.security.categories}
    current_scores = {c.category: c.score for c in current.security.categories}
    shared = sorted(set(baseline_scores) & set(current_scores))

    deltas: list[MetricDelta] = []
    for category in shared:
        base_val = baseline_scores[category]
        cur_val = current_scores[category]
        pct = _delta_pct(base_val, cur_val)
        regressed = pct is not None and pct < 0 and abs(pct) > max_relative_drop
        reason = (
            f"Security category '{category}' dropped {abs(pct) * 100:.1f}% "
            f"(limit {max_relative_drop * 100:.0f}%)"
            if regressed and pct is not None
            else ""
        )
        deltas.append(
            MetricDelta(
                name=f"Security: {category}",
                baseline=base_val,
                current=cur_val,
                delta=cur_val - base_val,
                delta_pct=pct,
                regressed=regressed,
                reason=reason,
            )
        )
    return deltas


def compare_reports(
    baseline: TestReport, current: TestReport, thresholds: ThresholdsConfig
) -> RegressionReport:
    deltas: list[MetricDelta] = []
    reasons: list[str] = []

    def add(
        name: str,
        base_val: float,
        cur_val: float,
        *,
        higher_is_worse: bool,
        max_relative_drop: float | None = None,
        max_relative_increase: float | None = None,
    ) -> None:
        pct = _delta_pct(base_val, cur_val)
        regressed = False
        reason = ""

        if not higher_is_worse and max_relative_drop is not None and pct is not None:
            if pct < 0 and abs(pct) > max_relative_drop:
                regressed = True
                reason = f"{name} dropped {abs(pct) * 100:.1f}% (limit {max_relative_drop * 100:.0f}%)"
        if higher_is_worse and max_relative_increase is not None and pct is not None:
            if pct > 0 and pct > max_relative_increase:
                regressed = True
                reason = f"{name} increased {pct * 100:.1f}% (limit {max_relative_increase * 100:.0f}%)"

        if regressed:
            reasons.append(reason)

        deltas.append(
            MetricDelta(
                name=name,
                baseline=base_val,
                current=cur_val,
                delta=cur_val - base_val,
                delta_pct=pct,
                regressed=regressed,
                reason=reason,
            )
        )

    add(
        "Task success",
        baseline.metrics.success_rate,
        current.metrics.success_rate,
        higher_is_worse=False,
        max_relative_drop=thresholds.regression.max_drop,
    )
    add(
        "Security score",
        baseline.metrics.security_score,
        current.metrics.security_score,
        higher_is_worse=False,
        max_relative_drop=thresholds.regression.max_drop,
    )
    if baseline.metrics.avg_latency_ms is not None and current.metrics.avg_latency_ms is not None:
        add(
            "Latency (ms)",
            baseline.metrics.avg_latency_ms,
            current.metrics.avg_latency_ms,
            higher_is_worse=True,
            max_relative_increase=thresholds.max_latency_increase,
        )
    add(
        "Cost (USD)",
        baseline.metrics.total_cost_usd,
        current.metrics.total_cost_usd,
        higher_is_worse=True,
        max_relative_increase=thresholds.max_cost_increase,
    )

    # Absolute floor checks, independent of the relative regression deltas above.
    if current.metrics.success_rate < thresholds.success_rate:
        reasons.append(
            f"Task success rate {current.metrics.success_rate * 100:.1f}% is below the "
            f"configured minimum {thresholds.success_rate * 100:.0f}%"
        )
    if current.metrics.security_score < thresholds.security_score * 100:
        reasons.append(
            f"Security score {current.metrics.security_score:.0f} is below the "
            f"configured minimum {thresholds.security_score * 100:.0f}"
        )

    # Per-test analytics: which specific tests flipped status.
    newly_failing, newly_passing, tests_added, tests_removed = _diff_test_outcomes(baseline, current)
    if newly_failing and thresholds.regression.fail_on_any_newly_failing:
        reasons.append(f"{len(newly_failing)} test(s) newly failing: {', '.join(newly_failing)}")

    # Per-security-category analytics: a category can regress even when
    # the overall security score stays within tolerance.
    category_deltas = _diff_security_categories(baseline, current, thresholds.regression.max_drop)
    for cat_delta in category_deltas:
        if cat_delta.regressed:
            reasons.append(cat_delta.reason)

    status = "FAIL" if reasons else "PASS"
    return RegressionReport(
        status=status,
        deltas=deltas,
        failure_reasons=reasons,
        newly_failing=newly_failing,
        newly_passing=newly_passing,
        tests_added=tests_added,
        tests_removed=tests_removed,
        category_deltas=category_deltas,
    )
