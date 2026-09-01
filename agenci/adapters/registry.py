"""Resolves an ``AgentConfig`` into a concrete adapter instance.

This is the only place in Agenci that maps a config string
(``agent.adapter``) to an implementation. Adding a new adapter means
adding one branch here — nothing else needs to know it exists.
"""

from __future__ import annotations

from agenci.adapters.anthropic_adapter import AnthropicAdapter
from agenci.adapters.autogen_adapter import AutoGenAdapter
from agenci.adapters.base import AgentAdapter
from agenci.adapters.crewai_adapter import CrewAIAdapter
from agenci.adapters.http_adapter import HttpAdapter
from agenci.adapters.langchain_adapter import LangChainAdapter
from agenci.adapters.mcp_adapter import MCPAdapter
from agenci.adapters.openai_adapter import OpenAIAdapter
from agenci.adapters.python_adapter import PythonAdapter
from agenci.config.models import AgentConfig

SUPPORTED_ADAPTERS = (
    "python",
    "http",
    "openai",
    "anthropic",
    "langchain",
    "crewai",
    "mcp",
    "autogen",
)


def build_adapter(config: AgentConfig) -> AgentAdapter:
    if config.adapter == "python":
        assert config.entrypoint is not None
        return PythonAdapter(config.entrypoint, timeout_seconds=config.timeout_seconds)
    if config.adapter == "http":
        assert config.url is not None
        return HttpAdapter(config.url, headers=config.headers, timeout_seconds=config.timeout_seconds)
    if config.adapter == "openai":
        assert config.model is not None
        return OpenAIAdapter(
            model=config.model,
            api_key_env=config.api_key_env,
            base_url=config.base_url,
            system_prompt=config.system_prompt,
            timeout_seconds=config.timeout_seconds,
        )
    if config.adapter == "langchain":
        assert config.entrypoint is not None
        return LangChainAdapter(
            config.entrypoint,
            input_key=config.input_key,
            output_key=config.output_key,
            timeout_seconds=config.timeout_seconds,
        )
    if config.adapter == "crewai":
        assert config.entrypoint is not None
        return CrewAIAdapter(
            config.entrypoint, input_key=config.input_key, timeout_seconds=config.timeout_seconds
        )
    if config.adapter == "mcp":
        assert config.mcp_command is not None
        assert config.mcp_tool is not None
        return MCPAdapter(
            command=config.mcp_command,
            tool=config.mcp_tool,
            args=config.mcp_args,
            env=config.mcp_env or None,
            timeout_seconds=config.timeout_seconds,
        )
    if config.adapter == "autogen":
        assert config.entrypoint is not None
        return AutoGenAdapter(config.entrypoint, timeout_seconds=config.timeout_seconds)
    if config.adapter == "anthropic":
        assert config.model is not None
        return AnthropicAdapter(
            model=config.model,
            api_key_env=config.api_key_env,
            base_url=config.base_url,
            system_prompt=config.system_prompt,
            max_tokens=config.max_tokens,
            anthropic_version=config.anthropic_version,
            timeout_seconds=config.timeout_seconds,
        )
    raise ValueError(
        f"Unsupported adapter {config.adapter!r}. Supported adapters: {SUPPORTED_ADAPTERS}. "
        f"See docs/adapters.md for how to add a new one."
    )
