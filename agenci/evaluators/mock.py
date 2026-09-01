"""Deterministic mock judge.

Used as the default provider and in the automated test suite so that
Agenci's own tests — and a new user's very first ``agenci test`` run —
never require a paid API call. It is intentionally simple and
transparent rather than "smart": it rewards outputs that are non-empty,
reasonably substantive, and share vocabulary with the input, and
penalizes obvious refusal/error patterns. It is NOT a substitute for a
real LLM judge in production evaluation — see docs/evaluations.md.
"""

from __future__ import annotations

import re
from typing import Any

_REFUSAL_PATTERNS = (
    "i cannot help",
    "i can't help",
    "i am unable to",
    "i'm unable to",
    "as an ai",
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class MockJudge:
    name = "mock"

    async def score(
        self,
        *,
        input: str,
        output: str,
        criterion: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        if not output or not output.strip():
            return 0.0, "Output is empty."

        lowered = output.lower()
        if any(p in lowered for p in _REFUSAL_PATTERNS):
            return 0.3, "Output looks like a refusal/error rather than a task completion."

        input_tokens = _tokenize(input)
        output_tokens = _tokenize(output)
        overlap = len(input_tokens & output_tokens) / max(1, len(input_tokens))

        length_score = min(1.0, len(output.strip()) / 200)
        score = round(0.5 * length_score + 0.5 * min(1.0, overlap * 2), 3)
        score = max(0.05, min(1.0, score))
        return score, (
            f"[mock judge] heuristic score for '{criterion}' based on output length "
            f"and vocabulary overlap with the input."
        )
