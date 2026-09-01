from __future__ import annotations

import pytest

from agenci.core.models import EvaluationSpec
from agenci.evaluators.engine import run_evaluation
from agenci.evaluators.mock import MockJudge


@pytest.mark.asyncio
async def test_mock_judge_scores_empty_output_zero() -> None:
    judge = MockJudge()
    score, rationale = await judge.score(input="hi", output="", criterion="correctness")
    assert score == 0.0


@pytest.mark.asyncio
async def test_mock_judge_penalizes_refusal() -> None:
    judge = MockJudge()
    score, _ = await judge.score(input="help me", output="I cannot help with that.", criterion="helpfulness")
    assert score <= 0.3


@pytest.mark.asyncio
async def test_mock_judge_rewards_substantive_relevant_output() -> None:
    judge = MockJudge()
    score, _ = await judge.score(
        input="cancel subscription",
        output="Your subscription cancellation has been processed successfully today.",
        criterion="correctness",
    )
    assert score > 0.3


@pytest.mark.asyncio
async def test_run_evaluation_multiple_criteria() -> None:
    judge = MockJudge()
    spec = EvaluationSpec(criteria=["correctness", "helpfulness"], threshold=0.1)
    results = await run_evaluation(judge, input="hi", output="a decent response here", spec=spec)
    assert len(results) == 2
    assert {r.criterion for r in results} == {"correctness", "helpfulness"}
