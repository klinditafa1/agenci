"""Pydantic models describing the ``agenci.yaml`` configuration file.

These models are intentionally provider-neutral and framework-neutral:
nothing in this module hard-codes a specific LLM vendor or agent
framework. Adapters and evaluators are selected by name/string and
resolved at runtime through a registry (see ``agenci.adapters`` and
``agenci.evaluators``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Human readable project name.")
    description: str | None = None


class AgentConfig(BaseModel):
    """Describes how Agenci should talk to the agent under test."""

    model_config = ConfigDict(extra="forbid")

    adapter: Literal["python", "http", "openai", "anthropic", "langchain", "crewai", "mcp", "autogen"] = (
        Field(..., description="Which adapter implementation to use.")
    )
    entrypoint: str | None = Field(
        default=None,
        description=(
            "For 'python': 'module.path:callable_name'. "
            "For 'langchain': 'module.path:callable_name' returning a Runnable. "
            "For 'crewai': 'module.path:callable_name' returning a Crew. "
            "For 'autogen': 'module.path:callable_name' returning an AutoGen agent or team."
        ),
    )
    url: str | None = Field(default=None, description="For the http adapter: base URL of the agent service.")
    headers: dict[str, str] = Field(default_factory=dict)
    model: str | None = Field(
        default=None, description="For the openai/anthropic adapters: model name to call."
    )
    base_url: str | None = Field(default=None, description="For the openai/anthropic adapters: API base URL.")
    api_key_env: str = Field(
        default="OPENAI_API_KEY",
        description=(
            "Environment variable holding the API key for the adapter, if needed. "
            "Defaults to ANTHROPIC_API_KEY automatically when adapter == 'anthropic' and "
            "this field is left unset."
        ),
    )
    timeout_seconds: float = Field(default=60.0, gt=0)
    system_prompt: str | None = None

    # 'anthropic' adapter options.
    max_tokens: int = Field(
        default=1024, gt=0, description="For 'anthropic': max_tokens passed to the Messages API."
    )
    anthropic_version: str = Field(
        default="2023-06-01", description="For 'anthropic': the anthropic-version header value."
    )

    # 'langchain' adapter options.
    input_key: str = Field(
        default="input",
        description="For 'langchain': the input variable name passed to the Runnable.",
    )
    output_key: str | None = Field(
        default=None,
        description=(
            "For 'langchain': key to extract from a dict-like Runnable output. If unset, "
            "Agenci checks 'output', 'answer', 'result' in order, then falls back to str()."
        ),
    )

    # 'mcp' adapter options.
    mcp_command: str | None = Field(
        default=None, description="For 'mcp': the command used to launch a stdio MCP server."
    )
    mcp_args: list[str] = Field(
        default_factory=list, description="For 'mcp': arguments passed to mcp_command."
    )
    mcp_env: dict[str, str] = Field(
        default_factory=dict,
        description="For 'mcp': extra environment variables for the server process.",
    )
    mcp_tool: str | None = Field(
        default=None, description="For 'mcp': name of the tool to invoke on each test case."
    )

    @model_validator(mode="after")
    def _validate_adapter_fields(self) -> AgentConfig:
        if self.adapter == "python" and not self.entrypoint:
            raise ValueError("agent.entrypoint is required when agent.adapter == 'python'")
        if self.adapter == "http" and not self.url:
            raise ValueError("agent.url is required when agent.adapter == 'http'")
        if self.adapter == "openai" and not self.model:
            raise ValueError("agent.model is required when agent.adapter == 'openai'")
        if self.adapter == "anthropic":
            if not self.model:
                raise ValueError("agent.model is required when agent.adapter == 'anthropic'")
            if self.api_key_env == "OPENAI_API_KEY":
                # Convenience default: api_key_env is shared across adapters and defaults
                # to OPENAI_API_KEY, which is never right for 'anthropic' — switch it
                # automatically unless the user explicitly set something else.
                self.api_key_env = "ANTHROPIC_API_KEY"
        if self.adapter == "langchain" and not self.entrypoint:
            raise ValueError("agent.entrypoint is required when agent.adapter == 'langchain'")
        if self.adapter == "crewai" and not self.entrypoint:
            raise ValueError("agent.entrypoint is required when agent.adapter == 'crewai'")
        if self.adapter == "autogen" and not self.entrypoint:
            raise ValueError("agent.entrypoint is required when agent.adapter == 'autogen'")
        if self.adapter == "mcp":
            if not self.mcp_command:
                raise ValueError("agent.mcp_command is required when agent.adapter == 'mcp'")
            if not self.mcp_tool:
                raise ValueError("agent.mcp_tool is required when agent.adapter == 'mcp'")
        return self


class TestsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directories: list[str] = Field(default_factory=lambda: ["tests"])


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["mock", "openai"] = "mock"
    model: str = "gpt-4.1-mini"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: JudgeConfig = Field(default_factory=JudgeConfig)


class MetricThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = None
    max: float | None = None


class RegressionThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_drop: float = Field(default=0.05, ge=0, le=1)
    fail_on_any_newly_failing: bool = Field(
        default=False,
        description=(
            "Fail 'agenci diff' if any individual test that passed in the baseline "
            "fails in the current run, even if aggregate metrics stay within max_drop."
        ),
    )


class ThresholdsConfig(BaseModel):
    """Configurable pass/fail gates used by ``agenci test`` and ``agenci diff``."""

    model_config = ConfigDict(extra="forbid")

    success_rate: float = Field(default=0.90, ge=0, le=1)
    security_score: float = Field(default=0.90, ge=0, le=1)
    max_cost_increase: float = Field(default=0.20, ge=0)
    max_latency_increase: float = Field(default=0.25, ge=0)
    regression: RegressionThresholds = Field(default_factory=RegressionThresholds)


class PricingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_per_1m: float = Field(..., ge=0)
    output_per_1m: float = Field(..., ge=0)


class CostConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: dict[str, PricingEntry] = Field(default_factory=dict)


class ExecutionConfig(BaseModel):
    """Controls how the test suite is executed."""

    model_config = ConfigDict(extra="forbid")

    concurrency: int = Field(
        default=1,
        ge=1,
        description=(
            "Max number of test cases run concurrently. Overridable per-invocation "
            "with --concurrency. Automatically clamped to 1 for adapters that hold "
            "state concurrent calls would corrupt (currently: autogen, crewai) — "
            "see docs/adapters.md."
        ),
    )


class TracingConfig(BaseModel):
    """Controls OpenTelemetry export of Agenci's AgentTrace records."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    otlp_endpoint: str | None = Field(
        default=None,
        description=(
            "OTLP/HTTP endpoint to export spans to, e.g. 'http://localhost:4318/v1/traces'. "
            "Falls back to the OTEL_EXPORTER_OTLP_ENDPOINT environment variable if unset."
        ),
    )
    console: bool = Field(
        default=False, description="Also print exported spans to the console (for debugging)."
    )
    service_name: str = "agenci"


class GitHubConfig(BaseModel):
    """Controls posting/updating a summary comment on a GitHub pull request."""

    model_config = ConfigDict(extra="forbid")

    post_pr_comment: bool = False
    token_env: str = Field(
        default="GITHUB_TOKEN", description="Environment variable holding a GitHub API token."
    )
    repo: str | None = Field(
        default=None,
        description="'owner/name'. Falls back to the GITHUB_REPOSITORY environment variable if unset.",
    )
    pr_number: int | None = Field(
        default=None,
        description="Pull request number. Auto-detected from GITHUB_EVENT_PATH if unset.",
    )


class AgenciConfig(BaseModel):
    """Root schema for ``agenci.yaml``."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    agent: AgentConfig
    tests: TestsConfig = Field(default_factory=TestsConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)

    @field_validator("project", mode="before")
    @classmethod
    def _project_from_str(cls, v: Any) -> Any:
        # Allow `project: my-agent` shorthand in addition to a full mapping.
        if isinstance(v, str):
            return {"name": v}
        return v


def config_path_candidates(start: Path) -> list[Path]:
    return [start / "agenci.yaml", start / "agenci.yml"]
