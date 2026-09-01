"""The report produced by a full ``agenci test`` / ``agenci security`` run."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from agenci.core.models import TestOutcome
from agenci.security.scoring import SecurityScoreReport


class Metrics(BaseModel):
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    success_rate: float = 0.0

    functional_total: int = 0
    functional_passed: int = 0

    security_total: int = 0
    security_passed: int = 0
    security_score: float = 100.0

    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class TestReport(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    project: str
    created_at: float = Field(default_factory=time.time)
    metrics: Metrics
    outcomes: list[TestOutcome]
    security: SecurityScoreReport | None = None

    def status(self, *, min_success_rate: float, min_security_score: float) -> str:
        ok = (
            self.metrics.success_rate >= min_success_rate
            and self.metrics.security_score >= min_security_score * 100
        )
        return "PASS" if ok else "FAIL"
