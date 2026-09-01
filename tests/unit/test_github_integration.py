from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from agenci.config.models import ThresholdsConfig
from agenci.core.models import TestOutcome
from agenci.integrations.github import (
    GitHubIntegrationError,
    build_pr_comment_markdown,
    detect_pr_number,
    detect_repo,
    post_or_update_pr_comment,
)
from agenci.reporting.builder import build_report
from agenci.reporting.diff import compare_reports


def _report(passed: bool = True, test_type: str = "functional"):
    outcomes = [
        TestOutcome(test_name="a", test_type=test_type, passed=passed, input="i", output="o"),
    ]
    return build_report("my-agent", outcomes)


def test_build_markdown_includes_marker_and_status() -> None:
    report = _report(passed=True)
    md = build_pr_comment_markdown("my-agent", report, min_success_rate=0.9, min_security_score=0.9)
    assert "<!-- agenci-report:my-agent -->" in md
    assert "Agenci checks passed" in md
    assert "Functional" in md


def test_build_markdown_reports_failure() -> None:
    report = _report(passed=False)
    md = build_pr_comment_markdown("my-agent", report, min_success_rate=0.9, min_security_score=0.9)
    assert "Agenci blocked this PR" in md
    assert "failing test(s)" in md
    assert "`a`" in md


def test_build_markdown_includes_security_suite() -> None:
    report = _report(passed=True, test_type="security")
    md = build_pr_comment_markdown("my-agent", report, min_success_rate=0.9, min_security_score=0.9)
    assert "Security" in md


def test_build_markdown_includes_regression_section() -> None:
    baseline = _report(passed=True)
    current = _report(passed=False)
    regression = compare_reports(baseline, current, ThresholdsConfig())
    md = build_pr_comment_markdown(
        "my-agent",
        current,
        min_success_rate=0.9,
        min_security_score=0.9,
        regression=regression,
    )
    assert "Regression" in md
    assert "Regression details" in md
    assert "Agenci blocked this PR" in md
    assert "newly failing" in md
    assert "`a`" in md


def test_detect_repo_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/my-agent")
    assert detect_repo() == "acme/my-agent"


def test_detect_repo_missing(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert detect_repo() is None


def test_detect_pr_number_from_event_path(monkeypatch, tmp_path: Path) -> None:
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps({"pull_request": {"number": 42}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    assert detect_pr_number() == 42


def test_detect_pr_number_from_ref_fallback(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_REF", "refs/pull/17/merge")
    assert detect_pr_number() == 17


def test_detect_pr_number_none_when_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    assert detect_pr_number() is None


@pytest.mark.asyncio
@respx.mock
async def test_post_creates_new_comment_when_none_exists() -> None:
    respx.get("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(200, json=[])
    )
    create_route = respx.post("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(201, json={"id": 999, "html_url": "https://github.com/x"})
    )

    result = await post_or_update_pr_comment(
        "hello", project="my-agent", repo="acme/agent", pr_number=5, token="tok"
    )
    assert create_route.called
    assert result["id"] == 999


@pytest.mark.asyncio
@respx.mock
async def test_post_updates_existing_comment_matched_by_marker() -> None:
    existing_body = "<!-- agenci-report:my-agent -->\nold content"
    respx.get("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(200, json=[{"id": 123, "body": existing_body}])
    )
    update_route = respx.patch("https://api.github.com/repos/acme/agent/issues/comments/123").mock(
        return_value=httpx.Response(200, json={"id": 123})
    )
    create_route = respx.post("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(201, json={"id": 999})
    )

    result = await post_or_update_pr_comment(
        "<!-- agenci-report:my-agent -->\nnew content",
        project="my-agent",
        repo="acme/agent",
        pr_number=5,
        token="tok",
    )
    assert update_route.called
    assert not create_route.called
    assert result["id"] == 123


@pytest.mark.asyncio
@respx.mock
async def test_post_ignores_comments_from_other_projects() -> None:
    other_body = "<!-- agenci-report:other-project -->\nnot mine"
    respx.get("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "body": other_body}])
    )
    create_route = respx.post("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(201, json={"id": 2})
    )

    result = await post_or_update_pr_comment(
        "body", project="my-agent", repo="acme/agent", pr_number=5, token="tok"
    )
    assert create_route.called
    assert result["id"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_post_raises_clean_error_on_http_failure() -> None:
    respx.get("https://api.github.com/repos/acme/agent/issues/5/comments").mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )
    with pytest.raises(GitHubIntegrationError):
        await post_or_update_pr_comment(
            "body", project="my-agent", repo="acme/agent", pr_number=5, token="bad-token"
        )
