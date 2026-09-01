"""Resolves config into a judge provider, and runs LLM-judge evaluations."""

from __future__ import annotations

from agenci.config.models import JudgeConfig
from agenci.core.models import EvaluationSpec, EvaluatorResult
from agenci.evaluators.base import JudgeProvider
from agenci.evaluators.mock import MockJudge
from agenci.evaluators.openai_judge import OpenAIJudge

SUPPORTED_JUDGES = ("mock", "openai")


def build_judge(config: JudgeConfig) -> JudgeProvider:
    if config.provider == "mock":
        return MockJudge()
    if config.provider == "openai":
        return OpenAIJudge(model=config.model, api_key_env=config.api_key_env, base_url=config.base_url)
    raise ValueError(f"Unsupported judge provider {config.provider!r}. Supported: {SUPPORTED_JUDGES}.")


async def run_evaluation(
    judge: JudgeProvider,
    *,
    input: str,
    output: str,
    spec: EvaluationSpec,
    context: dict | None = None,
) -> list[EvaluatorResult]:
    results: list[EvaluatorResult] = []
    for criterion in spec.criteria:
        score, rationale = await judge.score(input=input, output=output, criterion=criterion, context=context)
        results.append(
            EvaluatorResult(
                criterion=criterion,
                score=score,
                passed=score >= spec.threshold,
                threshold=spec.threshold,
                rationale=rationale,
            )
        )
    return results
