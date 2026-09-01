"""Data models shared across the test runner, evaluators, and reporting."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssertionType(str, Enum):
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX = "regex"
    EXACT = "exact"
    JSON_SCHEMA = "json_schema"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    CUSTOM_PYTHON = "custom_python"


class Assertion(BaseModel):
    """A single functional assertion.

    Exactly one of the recognized keys should be set; extra keys are
    rejected up front by config validation via the test-file loader.
    """

    model_config = ConfigDict(extra="allow")

    contains: str | None = None
    not_contains: str | None = None
    regex: str | None = None
    exact: str | None = None
    json_schema: dict[str, Any] | None = None
    semantic_similarity: str | None = None
    similarity_threshold: float = 0.75
    custom_python: str | None = None  # "module.path:function_name"

    def assertion_type(self) -> AssertionType:
        for field, kind in (
            ("contains", AssertionType.CONTAINS),
            ("not_contains", AssertionType.NOT_CONTAINS),
            ("regex", AssertionType.REGEX),
            ("exact", AssertionType.EXACT),
            ("json_schema", AssertionType.JSON_SCHEMA),
            ("semantic_similarity", AssertionType.SEMANTIC_SIMILARITY),
            ("custom_python", AssertionType.CUSTOM_PYTHON),
        ):
            if getattr(self, field) is not None:
                return kind
        raise ValueError(f"Assertion has no recognized key: {self.model_dump()}")


class EvaluationSpec(BaseModel):
    """Inline LLM-judge evaluation attached to a single test case."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["llm_judge"] = "llm_judge"
    criteria: list[str] = Field(default_factory=lambda: ["correctness"])
    threshold: float = 0.80


class SecurityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_tools: list[str] | None = None
    forbidden_tools: list[str] = Field(default_factory=list)
    forbidden_output_patterns: list[str] = Field(default_factory=list)
    max_tool_calls: int | None = None

    required_tools: list[str] = Field(
        default_factory=list,
        description="Tools that MUST appear among the agent's tool calls for this test.",
    )
    sensitive_tools: list[str] = Field(
        default_factory=list,
        description=(
            "Tools considered capable of irreversible or exfiltration-prone actions "
            "(e.g. send_email, http_request, write_file). Used by "
            "block_input_echo_to_sensitive_tools."
        ),
    )
    block_input_echo_to_sensitive_tools: bool = Field(
        default=False,
        description=(
            "Flag any call to a sensitive_tools entry whose arguments contain the "
            "test's raw input text verbatim — a heuristic for indirect prompt "
            "injection leading to data exfiltration via a tool call."
        ),
    )
    check_pii_leakage: bool = Field(
        default=False,
        description=(
            "Scan the agent's output against a built-in library of sensitive-data "
            "patterns (credit card, SSN, API keys, private key headers, JWTs)."
        ),
    )
    max_output_length: int | None = Field(
        default=None,
        description="Flag outputs longer than this many characters (unbounded output check).",
    )


class TestCase(BaseModel):
    """A single functional or security test case, as loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["functional", "security"] = "functional"
    category: str | None = Field(
        default=None,
        description=(
            "Security sub-category, e.g. prompt_injection, tool_authorization, "
            "sensitive_data_exposure. Only meaningful when type == 'security'."
        ),
    )
    input: str
    context: dict[str, Any] = Field(default_factory=dict)
    assertions: list[Assertion] = Field(default_factory=list)
    evaluation: EvaluationSpec | None = None
    policy: SecurityPolicy | None = None
    tags: list[str] = Field(default_factory=list)
    source_file: str | None = None


class AssertionResult(BaseModel):
    assertion: str
    passed: bool
    detail: str = ""


class EvaluatorResult(BaseModel):
    criterion: str
    score: float
    passed: bool
    threshold: float
    rationale: str = ""


class SecurityFinding(BaseModel):
    category: str
    severity: Literal["low", "medium", "high", "critical"]
    passed: bool
    description: str
    evidence: str = ""


class TestOutcome(BaseModel):
    """The full result of executing one TestCase once."""

    test_name: str
    test_type: Literal["functional", "security"]
    passed: bool
    input: str
    output: str | None
    error: str | None = None
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    evaluator_results: list[EvaluatorResult] = Field(default_factory=list)
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    latency_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    trace_run_id: str | None = None
