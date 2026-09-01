"""LLM-as-judge implementation backed by an OpenAI-compatible chat API."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

_JUDGE_SYSTEM_PROMPT = """You are an impartial evaluator for AI agent outputs.
Score the AGENT OUTPUT against the given CRITERION on a scale from 0.0 to 1.0.
Respond with ONLY a JSON object: {"score": <float 0-1>, "rationale": "<one sentence>"}."""


class OpenAIJudgeError(Exception):
    pass


class OpenAIJudge:
    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise OpenAIJudgeError(
                f"Environment variable {api_key_env} is not set; the openai judge "
                f"provider requires an API key. Use 'judge.provider: mock' to run "
                f"without one."
            )
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url or "https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def score(
        self,
        *,
        input: str,
        output: str,
        criterion: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        user_prompt = f"CRITERION: {criterion}\n\nAGENT INPUT:\n{input}\n\nAGENT OUTPUT:\n{output}"
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            score = float(parsed["score"])
            rationale = str(parsed.get("rationale", ""))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise OpenAIJudgeError(
                f"Judge model returned a response Agenci could not parse: {content!r} ({exc})"
            ) from exc
        return max(0.0, min(1.0, score)), rationale

    async def aclose(self) -> None:
        await self._client.aclose()
