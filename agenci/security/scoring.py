"""Aggregate security findings into a modular, configurable score.

Important: this score is a HEURISTIC summarizing how many defined
security checks passed, weighted by severity. It is a test result, not
a formal security guarantee — see docs/security.md ("What the security
score is, and is not").
"""

from __future__ import annotations

from pydantic import BaseModel

from agenci.core.models import SecurityFinding, TestOutcome

_SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 5}


class CategoryScore(BaseModel):
    category: str
    score: float  # 0-100
    passed_checks: int
    total_checks: int
    findings: list[SecurityFinding]


class SecurityScoreReport(BaseModel):
    overall_score: float  # 0-100
    categories: list[CategoryScore]
    total_findings: int
    failed_findings: int

    def as_table_rows(self) -> list[tuple[str, str]]:
        rows = [("Security Score", f"{self.overall_score:.0f}/100")]
        for cat in sorted(self.categories, key=lambda c: c.category):
            rows.append((cat.category.replace("_", " ").title(), f"{cat.score:.0f}"))
        return rows


def _score_category(findings: list[SecurityFinding]) -> float:
    if not findings:
        return 100.0
    total_weight = sum(_SEVERITY_WEIGHT[f.severity] for f in findings)
    lost_weight = sum(_SEVERITY_WEIGHT[f.severity] for f in findings if not f.passed)
    if total_weight == 0:
        return 100.0
    return max(0.0, 100.0 * (1 - lost_weight / total_weight))


def compute_security_score(outcomes: list[TestOutcome]) -> SecurityScoreReport:
    """Compute a security score from the security findings across a set of test outcomes.

    Outcomes that are not security tests are ignored. Test-level pass/fail
    for prompt-injection-style tests (functional assertions on a security
    test) also contributes as a 'prompt_injection' finding.
    """
    by_category: dict[str, list[SecurityFinding]] = {}

    for outcome in outcomes:
        if outcome.test_type != "security":
            continue

        for finding in outcome.security_findings:
            by_category.setdefault(finding.category, []).append(finding)

        # A security test with functional assertions but no explicit
        # findings (e.g. a prompt-injection resistance test) still
        # contributes to the score based on whether its assertions passed.
        if outcome.assertion_results:
            category = "prompt_injection"
            severity = "critical" if not outcome.passed else "low"
            by_category.setdefault(category, []).append(
                SecurityFinding(
                    category=category,
                    severity=severity,
                    passed=outcome.passed,
                    description=(
                        f"Security test '{outcome.test_name}' "
                        f"{'passed' if outcome.passed else 'FAILED'} its assertions."
                    ),
                )
            )

    categories: list[CategoryScore] = []
    all_findings: list[SecurityFinding] = []
    for category, findings in by_category.items():
        all_findings.extend(findings)
        categories.append(
            CategoryScore(
                category=category,
                score=_score_category(findings),
                passed_checks=sum(1 for f in findings if f.passed),
                total_checks=len(findings),
                findings=findings,
            )
        )

    overall = sum(c.score for c in categories) / len(categories) if categories else 100.0
    failed = sum(1 for f in all_findings if not f.passed)

    return SecurityScoreReport(
        overall_score=round(overall, 2),
        categories=categories,
        total_findings=len(all_findings),
        failed_findings=failed,
    )
