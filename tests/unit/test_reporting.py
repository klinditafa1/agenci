from __future__ import annotations

from agenci.config.models import ThresholdsConfig
from agenci.core.models import TestOutcome
from agenci.reporting.builder import build_report
from agenci.reporting.diff import compare_reports


def _outcome(name: str, passed: bool, latency_ms: float = 100.0, cost: float = 0.001) -> TestOutcome:
    return TestOutcome(
        test_name=name,
        test_type="functional",
        passed=passed,
        input="in",
        output="out",
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
    )


def test_build_report_success_rate() -> None:
    outcomes = [_outcome("a", True), _outcome("b", True), _outcome("c", False)]
    report = build_report("proj", outcomes)
    assert report.metrics.total_tests == 3
    assert report.metrics.passed_tests == 2
    assert round(report.metrics.success_rate, 4) == round(2 / 3, 4)


def test_build_report_empty_outcomes() -> None:
    report = build_report("proj", [])
    assert report.metrics.total_tests == 0
    assert report.metrics.success_rate == 1.0


def test_status_pass_and_fail() -> None:
    good = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    assert good.status(min_success_rate=0.9, min_security_score=0.9) == "PASS"

    bad = build_report("proj", [_outcome("a", True), _outcome("b", False)])
    assert bad.status(min_success_rate=0.9, min_security_score=0.9) == "FAIL"


def test_diff_detects_success_rate_regression() -> None:
    baseline = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    current = build_report("proj", [_outcome("a", True), _outcome("b", False)])
    thresholds = ThresholdsConfig()
    regression = compare_reports(baseline, current, thresholds)
    assert regression.status == "FAIL"
    assert any("Task success" in r for r in regression.failure_reasons)


def test_diff_detects_cost_increase() -> None:
    baseline = build_report("proj", [_outcome("a", True, cost=0.01)])
    current = build_report("proj", [_outcome("a", True, cost=0.05)])
    thresholds = ThresholdsConfig(max_cost_increase=0.2)
    regression = compare_reports(baseline, current, thresholds)
    assert regression.status == "FAIL"
    assert any("Cost" in r for r in regression.failure_reasons)


def test_diff_passes_when_stable() -> None:
    baseline = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    current = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    thresholds = ThresholdsConfig()
    regression = compare_reports(baseline, current, thresholds)
    assert regression.status == "PASS"
    assert regression.failure_reasons == []


def test_diff_detects_latency_increase() -> None:
    baseline = build_report("proj", [_outcome("a", True, latency_ms=100)])
    current = build_report("proj", [_outcome("a", True, latency_ms=500)])
    thresholds = ThresholdsConfig(max_latency_increase=0.25)
    regression = compare_reports(baseline, current, thresholds)
    assert regression.status == "FAIL"


def test_diff_identifies_newly_failing_test() -> None:
    baseline = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    current = build_report("proj", [_outcome("a", True), _outcome("b", False)])
    regression = compare_reports(baseline, current, ThresholdsConfig())
    assert regression.newly_failing == ["b"]
    assert regression.newly_passing == []


def test_diff_identifies_newly_passing_test() -> None:
    baseline = build_report("proj", [_outcome("a", True), _outcome("b", False)])
    current = build_report("proj", [_outcome("a", True), _outcome("b", True)])
    regression = compare_reports(baseline, current, ThresholdsConfig())
    assert regression.newly_passing == ["b"]
    assert regression.newly_failing == []
    # A test flipping to pass doesn't fail the run on its own.
    assert regression.status == "PASS"


def test_diff_identifies_added_and_removed_tests() -> None:
    baseline = build_report("proj", [_outcome("a", True), _outcome("old_test", True)])
    current = build_report("proj", [_outcome("a", True), _outcome("new_test", True)])
    regression = compare_reports(baseline, current, ThresholdsConfig())
    assert regression.tests_added == ["new_test"]
    assert regression.tests_removed == ["old_test"]


def test_diff_fail_on_any_newly_failing_opt_in() -> None:
    # Two tests baseline, one flips to failing — aggregate drop is 50%,
    # well within the default 5% max_drop tolerance would normally allow
    # for a much larger suite, but the opt-in flag catches it directly.
    baseline = build_report("proj", [_outcome(f"t{i}", True) for i in range(20)])
    outcomes = [_outcome(f"t{i}", True) for i in range(20)]
    outcomes[0] = _outcome("t0", False)
    current = build_report("proj", outcomes)

    lenient_thresholds = ThresholdsConfig(success_rate=0.5)
    lenient_thresholds.regression.max_drop = 0.5  # tolerate the aggregate drop
    regression_off = compare_reports(baseline, current, lenient_thresholds)
    assert regression_off.status == "PASS"
    assert regression_off.newly_failing == ["t0"]

    strict_thresholds = ThresholdsConfig(success_rate=0.5)
    strict_thresholds.regression.max_drop = 0.5
    strict_thresholds.regression.fail_on_any_newly_failing = True
    regression_on = compare_reports(baseline, current, strict_thresholds)
    assert regression_on.status == "FAIL"
    assert any("t0" in r for r in regression_on.failure_reasons)


def test_diff_flags_security_category_regression_even_when_overall_stable() -> None:
    from agenci.core.models import SecurityFinding

    baseline_findings_a = [
        SecurityFinding(category="tool_authorization", severity="low", passed=True, description="ok")
    ]
    baseline_findings_b = [
        SecurityFinding(category="data_exfiltration", severity="low", passed=True, description="ok")
    ]
    current_findings_a = [
        SecurityFinding(category="tool_authorization", severity="low", passed=True, description="ok")
    ]
    current_findings_b = [
        SecurityFinding(category="data_exfiltration", severity="critical", passed=False, description="leak")
    ]

    baseline_outcomes = [
        TestOutcome(
            test_name="sec_a",
            test_type="security",
            passed=True,
            input="i",
            output="o",
            security_findings=baseline_findings_a,
        ),
        TestOutcome(
            test_name="sec_b",
            test_type="security",
            passed=True,
            input="i",
            output="o",
            security_findings=baseline_findings_b,
        ),
    ]
    current_outcomes = [
        TestOutcome(
            test_name="sec_a",
            test_type="security",
            passed=True,
            input="i",
            output="o",
            security_findings=current_findings_a,
        ),
        TestOutcome(
            test_name="sec_b",
            test_type="security",
            passed=False,
            input="i",
            output="o",
            security_findings=current_findings_b,
        ),
    ]

    baseline = build_report("proj", baseline_outcomes)
    current = build_report("proj", current_outcomes)
    regression = compare_reports(baseline, current, ThresholdsConfig())

    category_names = {d.name for d in regression.category_deltas}
    assert "Security: data_exfiltration" in category_names
    exfil_delta = next(d for d in regression.category_deltas if d.name == "Security: data_exfiltration")
    assert exfil_delta.regressed
    assert regression.status == "FAIL"
