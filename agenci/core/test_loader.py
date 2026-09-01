"""Discovers and loads test-case YAML files from configured directories."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agenci.core.models import TestCase


class TestLoadError(Exception):
    pass


def _iter_yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in (".yaml", ".yml"))


def load_test_file(path: Path) -> list[TestCase]:
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise TestLoadError(f"Could not parse {path} as YAML:\n{exc}") from exc

    # A file may define a single test case (a mapping with 'name') or a
    # list of test cases (a top-level YAML list, or {"tests": [...]}).
    if isinstance(raw, dict) and "tests" in raw:
        entries = raw["tests"]
    elif isinstance(raw, list):
        entries = raw
    elif isinstance(raw, dict):
        entries = [raw]
    else:
        raise TestLoadError(f"{path}: expected a mapping or list of test cases, got {type(raw)}")

    cases: list[TestCase] = []
    for entry in entries:
        try:
            case = TestCase.model_validate(entry)
        except ValidationError as exc:
            lines = [f"Invalid test case in {path}:"]
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "<root>"
                lines.append(f"  - {loc}: {err['msg']}")
            raise TestLoadError("\n".join(lines)) from exc
        case.source_file = str(path)
        cases.append(case)
    return cases


def load_all_tests(directories: list[str], root: Path | None = None) -> list[TestCase]:
    root = root or Path.cwd()
    cases: list[TestCase] = []
    seen_files: list[Path] = []
    for directory in directories:
        for file in _iter_yaml_files(root / directory):
            seen_files.append(file)
            cases.extend(load_test_file(file))

    if not seen_files:
        dirs = ", ".join(directories)
        raise TestLoadError(
            f"No test files found in configured directories: {dirs}\n"
            f"Add a .yaml test file, or run 'agenci init' to scaffold examples."
        )
    return cases


def filter_by_type(cases: list[TestCase], test_type: str) -> list[TestCase]:
    return [c for c in cases if c.type == test_type]
