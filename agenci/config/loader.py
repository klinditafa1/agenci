"""Loading and validating ``agenci.yaml``."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agenci.config.models import AgenciConfig, config_path_candidates


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or fails validation.

    The message is written to be read directly by a developer in a
    terminal — no stack trace required to understand what went wrong.
    """


def find_config_file(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    for candidate in config_path_candidates(start):
        if candidate.exists():
            return candidate
    raise ConfigError(
        f"No agenci.yaml found in {start}.\nRun 'agenci init' to create one, or pass --config <path>."
    )


def _format_validation_error(exc: ValidationError, source: Path) -> str:
    lines = [f"Invalid configuration in {source}:"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        msg = err["msg"]
        lines.append(f"  - {loc}: {msg}")
    lines.append("")
    lines.append("See docs/configuration.md for the full schema.")
    return "\n".join(lines)


def load_config(path: Path | None = None) -> AgenciConfig:
    """Load and validate an ``agenci.yaml`` file.

    Raises:
        ConfigError: if the file is missing, is not valid YAML, or does
            not conform to the Agenci configuration schema.
    """
    resolved = path or find_config_file()
    if not resolved.exists():
        raise ConfigError(f"Configuration file not found: {resolved}")

    try:
        raw = yaml.safe_load(resolved.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {resolved} as YAML:\n{exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(
            f"{resolved} must contain a YAML mapping at the top level, got {type(raw).__name__}."
        )

    try:
        return AgenciConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc, resolved)) from exc
