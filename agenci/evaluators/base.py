"""Provider-neutral LLM-as-judge interface.

Agenci does not hard-code a judge model or vendor. Anything that can
score an (input, output) pair against a named criterion and return a
0-1 score plus a short rationale can be plugged in here.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JudgeProvider(Protocol):
    name: str

    async def score(
        self,
        *,
        input: str,
        output: str,
        criterion: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        """Return (score in [0, 1], short rationale) for one criterion."""
        ...
