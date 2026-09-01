"""Posts (and updates) a summary comment on a GitHub pull request.

Deliberately built directly against the GitHub REST API with
``httpx`` — no GitHub SDK dependency — since the surface area needed
(list issue comments, create one, update one) is small and stable.

The comment is idempotent across re-runs of the same PR: every comment
Agenci posts carries a hidden HTML marker
(``<!-- agenci-report:{project} -->``), so a second run on the same PR
updates the existing comment instead of piling up duplicates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from agenci.reporting.diff import RegressionReport
from agenci.reporting.models import TestReport

DEFAULT_API_BASE = "https://api.github.com"


class GitHubIntegrationError(Exception):
    pass


def _marker(project: str) -> str:
    return f"<!-- agenci-report:{project} -->"


def detect_repo() -> str | None:
    return os.environ.get("GITHUB_REPOSITORY")


def detect_pr_number() -> int | None:
    """Best-effort PR number detection for GitHub Actions.

    Checks the standard `pull_request`/`pull_request_target` event
    payload first (via GITHUB_EVENT_PATH), then falls back to parsing
    GITHUB_REF for the `refs/pull/<N>/merge` pattern some other
    triggers use.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).exists():
        try:
            event = json.loads(Path(event_path).read_text())
        except (json.JSONDecodeError, OSError):
            event = {}
        pr = event.get("pull_request") or {}
        if isinstance(pr.get("number"), int):
            return pr["number"]
        if isinstance(event.get("number"), int):
            return event["number"]

    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/pull/"):
        parts = ref.split("/")
        if len(parts) >= 3 and parts[2].isdigit():
            return int(parts[2])
    return None


def _status_line(label: str, ok: bool | None) -> str:
    if ok is None:
        return f"| {label} | — |"
    return f"| {label} | {'✅ PASS' if ok else '❌ FAIL'} |"


def build_pr_comment_markdown(
    project: str,
    report: TestReport,
    *,
    min_success_rate: float,
    min_security_score: float,
    security_report: TestReport | None = None,
    regression: RegressionReport | None = None,
) -> str:
    """Builds the markdown body for a PR comment summarizing one or more
    Agenci reports, in the style of the spec's "PR experience" example:
    a per-suite pass/fail table, the security score, and an overall
    verdict."""
    m = report.metrics
    overall_status = report.status(min_success_rate=min_success_rate, min_security_score=min_security_score)

    lines: list[str] = [_marker(project)]
    lines.append(f"## Agenci — {project}")
    lines.append("")
    lines.append(f"**{m.total_tests} evaluation(s) completed**")
    lines.append("")
    lines.append("| Suite | Status |")
    lines.append("|---|---|")

    if m.functional_total:
        lines.append(_status_line("Functional", m.functional_passed == m.functional_total))

    security_metrics = security_report.metrics if security_report is not None else m
    if security_metrics.security_total:
        lines.append(_status_line("Security", security_metrics.security_score >= min_security_score * 100))

    if regression is not None:
        lines.append(_status_line("Regression", regression.status == "PASS"))

    lines.append("")
    lines.append(f"- Success rate: **{m.success_rate * 100:.1f}%**")
    lines.append(f"- Security score: **{security_metrics.security_score:.0f}/100**")
    if m.avg_latency_ms is not None:
        lines.append(f"- Avg latency: **{m.avg_latency_ms:.0f}ms**")
    lines.append(f"- Estimated cost: **${m.total_cost_usd:.4f}**")

    failed = [o for o in report.outcomes if not o.passed]
    if security_report is not None:
        failed += [o for o in security_report.outcomes if not o.passed]
    if failed:
        lines.append("")
        lines.append(f"<details><summary>{len(failed)} failing test(s)</summary>")
        lines.append("")
        for outcome in failed:
            lines.append(f"- ❌ `{outcome.test_name}`")
            for a in outcome.assertion_results:
                if not a.passed:
                    lines.append(f"  - {a.assertion}: {a.detail}")
            for sf in outcome.security_findings:
                if not sf.passed:
                    lines.append(f"  - [{sf.severity}] {sf.description}")
            if outcome.error:
                lines.append(f"  - error: {outcome.error}")
        lines.append("")
        lines.append("</details>")

    if regression is not None and (
        regression.failure_reasons
        or regression.newly_failing
        or regression.newly_passing
        or regression.tests_added
        or regression.tests_removed
    ):
        lines.append("")
        lines.append("<details><summary>Regression details</summary>")
        lines.append("")
        for d in regression.deltas:
            marker = " ⚠️" if d.regressed else ""
            lines.append(f"- {d.name}: {d.baseline:.4f} → {d.current:.4f}{marker}")

        if regression.category_deltas:
            lines.append("")
            lines.append("**Security category deltas:**")
            for d in regression.category_deltas:
                marker = " ⚠️" if d.regressed else ""
                cat = d.name.removeprefix("Security: ")
                lines.append(f"- {cat}: {d.baseline:.0f} → {d.current:.0f}{marker}")

        if regression.newly_failing:
            lines.append("")
            lines.append(f"**{len(regression.newly_failing)} test(s) newly failing:**")
            for name in regression.newly_failing:
                lines.append(f"- ❌ `{name}`")

        if regression.newly_passing:
            lines.append("")
            lines.append(f"**{len(regression.newly_passing)} test(s) newly passing:**")
            for name in regression.newly_passing:
                lines.append(f"- ✅ `{name}`")

        if regression.tests_added:
            lines.append("")
            lines.append(f"Tests added since baseline: {', '.join(f'`{n}`' for n in regression.tests_added)}")
        if regression.tests_removed:
            lines.append("")
            lines.append(
                f"Tests removed since baseline: {', '.join(f'`{n}`' for n in regression.tests_removed)}"
            )

        if regression.failure_reasons:
            lines.append("")
            for reason in regression.failure_reasons:
                lines.append(f"- {reason}")
        lines.append("")
        lines.append("</details>")

    lines.append("")
    combined_pass = overall_status == "PASS" and (regression is None or regression.status == "PASS")
    lines.append("✅ **Agenci checks passed.**" if combined_pass else "❌ **Agenci blocked this PR.**")

    return "\n".join(lines)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def post_or_update_pr_comment(
    markdown: str,
    *,
    project: str,
    repo: str,
    pr_number: int,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    timeout_seconds: float = 30.0,
) -> dict:
    """Posts `markdown` as a PR comment, updating a previous Agenci
    comment on the same PR (matched by project marker) if one exists."""
    marker = _marker(project)
    async with httpx.AsyncClient(
        base_url=api_base, headers=_headers(token), timeout=timeout_seconds
    ) as client:
        try:
            list_resp = await client.get(
                f"/repos/{repo}/issues/{pr_number}/comments", params={"per_page": 100}
            )
            list_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise GitHubIntegrationError(f"Could not list PR comments: {exc}") from exc

        existing_id: int | None = None
        for comment in list_resp.json():
            if marker in (comment.get("body") or ""):
                existing_id = comment["id"]
                break

        try:
            if existing_id is not None:
                resp = await client.patch(
                    f"/repos/{repo}/issues/comments/{existing_id}", json={"body": markdown}
                )
            else:
                resp = await client.post(
                    f"/repos/{repo}/issues/{pr_number}/comments", json={"body": markdown}
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise GitHubIntegrationError(f"Could not post/update PR comment: {exc}") from exc

        return resp.json()
