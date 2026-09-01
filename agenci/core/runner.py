"""The engine that actually executes test cases against an agent.

This is the piece everything else (CLI, GitHub Action, dashboard) sits
on top of: given an adapter, an optional judge, and a list of test
cases, run each one and produce a TestOutcome + AgentTrace.
"""

from __future__ import annotations

import asyncio
import time

from agenci.adapters.base import AgentAdapter
from agenci.core.assertions import run_assertion
from agenci.core.cost import CostEstimator
from agenci.core.models import (
    AssertionResult,
    AssertionType,
    EvaluatorResult,
    SecurityFinding,
    TestCase,
    TestOutcome,
)
from agenci.evaluators.base import JudgeProvider
from agenci.evaluators.engine import run_evaluation
from agenci.security.policy import evaluate_policy
from agenci.tracing.schema import AgentTrace, ModelCall, ToolCall

# Adapter class names known to hold state that concurrent calls would
# corrupt: AutoGenAdapter reuses one agent/team instance and resets its
# conversation history in place between calls (two concurrent .run()
# calls would race on that reset); CrewAIAdapter subscribes handlers to
# CrewAI's process-global event bus per call (two concurrent calls would
# each see the other's tool-call events). Both are documented in
# docs/adapters.md. Checked by class name rather than isinstance to
# avoid a hard import dependency on optional adapter packages here.
_CONCURRENCY_UNSAFE_ADAPTER_CLASS_NAMES = frozenset({"AutoGenAdapter", "CrewAIAdapter"})


class TestRunner:
    def __init__(
        self,
        adapter: AgentAdapter,
        judge: JudgeProvider | None = None,
        cost_estimator: CostEstimator | None = None,
    ) -> None:
        self.adapter = adapter
        self.judge = judge
        self.cost_estimator = cost_estimator or CostEstimator()
        # Set by run_all() to the concurrency actually used, which may be
        # lower than requested — see _effective_concurrency().
        self.last_effective_concurrency: int = 1
        self.concurrency_note: str | None = None

    async def run_case(self, case: TestCase) -> tuple[TestOutcome, AgentTrace]:
        trace = AgentTrace(test_name=case.name, input=case.input, context=case.context)

        start = time.perf_counter()
        response = await self.adapter.run(case.input, case.context)
        latency_ms = (time.perf_counter() - start) * 1000
        trace.latency_ms = latency_ms
        trace.output = response.output

        for tc in response.tool_calls:
            trace.record_tool_call(
                ToolCall(
                    tool=tc.tool,
                    arguments=tc.arguments,
                    result=tc.result,
                    latency_ms=tc.latency_ms,
                    error=tc.error,
                )
            )

        estimated_cost = None
        if response.model:
            estimated_cost = self.cost_estimator.estimate_usd(
                response.model, response.input_tokens or 0, response.output_tokens or 0
            )
        trace.record_model_call(
            ModelCall(
                provider=response.provider or "unknown",
                model=response.model or "unknown",
                latency_ms=latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                estimated_cost_usd=estimated_cost,
            )
        )

        if response.error:
            outcome = TestOutcome(
                test_name=case.name,
                test_type=case.type,
                passed=False,
                input=case.input,
                output=None,
                error=response.error,
                latency_ms=latency_ms,
                trace_run_id=trace.run_id,
            )
            trace.error = response.error
            return outcome, trace

        assertion_results: list[AssertionResult] = []
        evaluator_results: list[EvaluatorResult] = []
        security_findings: list[SecurityFinding] = []

        for assertion in case.assertions:
            if assertion.assertion_type() is AssertionType.SEMANTIC_SIMILARITY:
                if self.judge is None:
                    assertion_results.append(
                        AssertionResult(
                            assertion="semantic_similarity",
                            passed=False,
                            detail="No judge provider configured for semantic_similarity assertions.",
                        )
                    )
                    continue
                score, rationale = await self.judge.score(
                    input=assertion.semantic_similarity or "",
                    output=response.output,
                    criterion="semantic_similarity_to_reference_text",
                )
                passed = score >= assertion.similarity_threshold
                assertion_results.append(
                    AssertionResult(
                        assertion=f"semantic_similarity >= {assertion.similarity_threshold}",
                        passed=passed,
                        detail=f"score={score:.2f}. {rationale}",
                    )
                )
            else:
                assertion_results.append(run_assertion(response.output, assertion))

        if case.evaluation is not None:
            if self.judge is None:
                evaluator_results.append(
                    EvaluatorResult(
                        criterion="(no judge configured)",
                        score=0.0,
                        passed=False,
                        threshold=case.evaluation.threshold,
                        rationale="No judge provider configured; set evaluation.judge in agenci.yaml.",
                    )
                )
            else:
                evaluator_results = await run_evaluation(
                    self.judge,
                    input=case.input,
                    output=response.output,
                    spec=case.evaluation,
                    context=case.context,
                )

        if case.policy is not None:
            security_findings = evaluate_policy(
                case.policy, response.output, response.tool_calls, input_text=case.input
            )

        passed = (
            all(a.passed for a in assertion_results)
            and all(e.passed for e in evaluator_results)
            and all(f.passed for f in security_findings)
        )

        trace.evaluator_results = [e.model_dump() for e in evaluator_results]
        trace.security_findings = [f.model_dump() for f in security_findings]

        outcome = TestOutcome(
            test_name=case.name,
            test_type=case.type,
            passed=passed,
            input=case.input,
            output=response.output,
            assertion_results=assertion_results,
            evaluator_results=evaluator_results,
            security_findings=security_findings,
            latency_ms=latency_ms,
            input_tokens=response.input_tokens or 0,
            output_tokens=response.output_tokens or 0,
            estimated_cost_usd=estimated_cost or 0.0,
            trace_run_id=trace.run_id,
        )
        return outcome, trace

    def _effective_concurrency(self, requested: int) -> tuple[int, str | None]:
        requested = max(1, requested)
        adapter_class_name = type(self.adapter).__name__
        if requested > 1 and adapter_class_name in _CONCURRENCY_UNSAFE_ADAPTER_CLASS_NAMES:
            note = (
                f"Concurrency clamped to 1: the '{adapter_class_name}' adapter shares "
                f"state (conversation history / a process-global event bus) across calls "
                f"that concurrent execution would corrupt. See docs/adapters.md."
            )
            return 1, note
        return requested, None

    async def run_all(
        self, cases: list[TestCase], concurrency: int = 1
    ) -> list[tuple[TestOutcome, AgentTrace]]:
        """Runs every test case, optionally overlapping up to `concurrency`
        agent calls at once.

        `concurrency` is automatically clamped to 1 for adapters known to
        hold state that concurrent calls would corrupt (see
        `_CONCURRENCY_UNSAFE_ADAPTER_CLASS_NAMES`); check
        `self.concurrency_note` after the call if you want to surface that
        to the user. Results are always returned in the same order as
        `cases`, regardless of completion order or concurrency.
        """
        effective, note = self._effective_concurrency(concurrency)
        self.last_effective_concurrency = effective
        self.concurrency_note = note

        if effective == 1:
            results = []
            for case in cases:
                results.append(await self.run_case(case))
            return results

        semaphore = asyncio.Semaphore(effective)

        async def _bounded(case: TestCase) -> tuple[TestOutcome, AgentTrace]:
            async with semaphore:
                return await self.run_case(case)

        return await asyncio.gather(*(_bounded(case) for case in cases))
