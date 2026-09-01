from __future__ import annotations

import pytest

from agenci.adapters.python_adapter import PythonAdapter
from agenci.core.models import Assertion, EvaluationSpec, SecurityPolicy, TestCase
from agenci.core.runner import TestRunner
from agenci.evaluators.mock import MockJudge


@pytest.mark.asyncio
async def test_functional_case_passes() -> None:
    adapter = PythonAdapter("sample_agent:run_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    case = TestCase(
        name="cancel",
        input="please cancel my subscription",
        assertions=[Assertion(contains="cancelled")],
    )
    results = await runner.run_all([case])
    outcome, trace = results[0]
    assert outcome.passed
    assert trace.output is not None


@pytest.mark.asyncio
async def test_functional_case_with_llm_judge() -> None:
    adapter = PythonAdapter("sample_agent:run_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    case = TestCase(
        name="cancel_eval",
        input="please cancel my subscription today",
        evaluation=EvaluationSpec(criteria=["correctness"], threshold=0.05),
    )
    results = await runner.run_all([case])
    outcome, _ = results[0]
    assert outcome.evaluator_results
    assert outcome.passed


@pytest.mark.asyncio
async def test_security_case_with_forbidden_tool() -> None:
    adapter = PythonAdapter("sample_agent:agent_with_tools")
    runner = TestRunner(adapter, judge=MockJudge())
    case = TestCase(
        name="no_shell",
        type="security",
        input="please delete everything",
        policy=SecurityPolicy(forbidden_tools=["shell"]),
    )
    results = await runner.run_all([case])
    outcome, _ = results[0]
    assert not outcome.passed
    assert any(f.category == "tool_authorization" for f in outcome.security_findings)


@pytest.mark.asyncio
async def test_broken_agent_produces_failed_outcome_not_exception() -> None:
    adapter = PythonAdapter("sample_agent:broken_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    case = TestCase(name="broken", input="hi")
    results = await runner.run_all([case])
    outcome, _ = results[0]
    assert not outcome.passed
    assert outcome.error is not None


@pytest.mark.asyncio
async def test_concurrency_reduces_wall_clock_time() -> None:
    import time

    adapter = PythonAdapter("sample_agent:slow_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    cases = [TestCase(name=f"t{i}", input=f"input {i}", context={"delay_seconds": 0.08}) for i in range(6)]

    start = time.perf_counter()
    await runner.run_all(cases, concurrency=1)
    sequential_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    await runner.run_all(cases, concurrency=6)
    concurrent_elapsed = time.perf_counter() - start

    # 6 cases * 0.08s ~= 0.48s sequential vs ~0.08s concurrent — allow generous
    # margin for CI scheduling jitter while still proving real overlap.
    assert concurrent_elapsed < sequential_elapsed / 2
    assert runner.last_effective_concurrency == 6


@pytest.mark.asyncio
async def test_concurrency_preserves_result_order_regardless_of_completion_order() -> None:
    adapter = PythonAdapter("sample_agent:slow_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    # First case takes longest, last case finishes first — if ordering were
    # completion-order instead of input-order, this would catch it.
    cases = [
        TestCase(name=f"t{i}", input=f"input {i}", context={"delay_seconds": 0.05 * (5 - i)})
        for i in range(5)
    ]
    results = await runner.run_all(cases, concurrency=5)
    assert [outcome.test_name for outcome, _trace in results] == [f"t{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_concurrency_one_is_default_and_backward_compatible() -> None:
    adapter = PythonAdapter("sample_agent:run_agent")
    runner = TestRunner(adapter, judge=MockJudge())
    case = TestCase(name="cancel", input="please cancel my subscription")
    results = await runner.run_all([case])  # no concurrency arg, as in existing callers
    assert results[0][0].passed
    assert runner.last_effective_concurrency == 1
    assert runner.concurrency_note is None


class _FakeAutoGenAdapter:
    """A stand-in with the exact class name TestRunner checks for, so this
    test doesn't require the real (optional) autogen-agentchat package."""

    __name__ = "AutoGenAdapter"

    async def run(self, input: str, context: dict | None = None):
        from agenci.adapters.base import AgentResponse

        return AgentResponse(output=f"ack: {input}")

    async def aclose(self) -> None:
        return None


_FakeAutoGenAdapter.__qualname__ = "AutoGenAdapter"
_FakeAutoGenAdapter.__name__ = "AutoGenAdapter"


@pytest.mark.asyncio
async def test_concurrency_clamped_for_stateful_framework_adapters() -> None:
    # type() reports the *defining* class's __name__, which we've set to
    # match what TestRunner checks for — this exercises the real clamp
    # logic in _effective_concurrency without needing autogen installed.
    FakeAdapter = type(
        "AutoGenAdapter",
        (),
        {
            "run": _FakeAutoGenAdapter.run,
            "aclose": _FakeAutoGenAdapter.aclose,
        },
    )
    adapter = FakeAdapter()
    runner = TestRunner(adapter, judge=MockJudge())
    cases = [TestCase(name=f"t{i}", input=f"in {i}") for i in range(3)]

    results = await runner.run_all(cases, concurrency=8)

    assert runner.last_effective_concurrency == 1
    assert runner.concurrency_note is not None
    assert "AutoGenAdapter" in runner.concurrency_note
    assert len(results) == 3
