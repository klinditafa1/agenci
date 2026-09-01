from __future__ import annotations

from pathlib import Path

import pytest

from agenci.config.loader import ConfigError, load_config


def _write(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def test_load_valid_config(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project:
  name: my-agent
agent:
  adapter: python
  entrypoint: agent:run_agent
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.project.name == "my-agent"
    assert cfg.agent.adapter == "python"
    assert cfg.thresholds.success_rate == 0.90


def test_project_shorthand(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: http
  url: http://localhost:9000
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.project.name == "my-agent"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    cfg_path = _write(tmp_path / "agenci.yaml", "project: [unterminated")
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_missing_required_field_gives_readable_error(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project:
  name: my-agent
agent:
  adapter: python
""",
    )
    with pytest.raises(ConfigError) as exc_info:
        load_config(cfg_path)
    message = str(exc_info.value)
    assert "entrypoint" in message


def test_python_adapter_requires_entrypoint(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: python
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: python
  entrypoint: agent:run_agent
totally_unknown_field: true
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_langchain_adapter_requires_entrypoint(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: langchain
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_langchain_adapter_valid_config(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: langchain
  entrypoint: agent:build_chain
  input_key: question
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.adapter == "langchain"
    assert cfg.agent.input_key == "question"


def test_crewai_adapter_requires_entrypoint(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: crewai
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_mcp_adapter_requires_command_and_tool(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: mcp
  mcp_command: python3
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_mcp_adapter_valid_config(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: mcp
  mcp_command: python3
  mcp_args: ["server.py"]
  mcp_tool: add
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.mcp_tool == "add"
    assert cfg.agent.mcp_args == ["server.py"]


def test_autogen_adapter_requires_entrypoint(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: autogen
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_autogen_adapter_valid_config(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: autogen
  entrypoint: agent:build_agent
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.adapter == "autogen"
    assert cfg.agent.entrypoint == "agent:build_agent"


def test_anthropic_adapter_requires_model(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: anthropic
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_anthropic_adapter_auto_sets_api_key_env(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: anthropic
  model: claude-sonnet-5
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.api_key_env == "ANTHROPIC_API_KEY"


def test_anthropic_adapter_respects_explicit_api_key_env(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: anthropic
  model: claude-sonnet-5
  api_key_env: MY_CUSTOM_KEY
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.api_key_env == "MY_CUSTOM_KEY"


def test_anthropic_adapter_default_max_tokens(tmp_path: Path) -> None:
    cfg_path = _write(
        tmp_path / "agenci.yaml",
        """
project: my-agent
agent:
  adapter: anthropic
  model: claude-sonnet-5
""",
    )
    cfg = load_config(cfg_path)
    assert cfg.agent.max_tokens == 1024
