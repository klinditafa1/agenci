from __future__ import annotations

from agenci.core.assertions import run_assertion
from agenci.core.models import Assertion


def test_contains_pass() -> None:
    result = run_assertion("hello world", Assertion(contains="world"))
    assert result.passed


def test_contains_fail() -> None:
    result = run_assertion("hello world", Assertion(contains="goodbye"))
    assert not result.passed


def test_not_contains_pass() -> None:
    result = run_assertion("hello world", Assertion(not_contains="goodbye"))
    assert result.passed


def test_not_contains_fail() -> None:
    result = run_assertion("I cannot help", Assertion(not_contains="cannot help"))
    assert not result.passed


def test_regex_pass() -> None:
    result = run_assertion("order #12345 confirmed", Assertion(regex=r"order #\d+"))
    assert result.passed


def test_regex_fail() -> None:
    result = run_assertion("no order here", Assertion(regex=r"order #\d+"))
    assert not result.passed


def test_exact_pass() -> None:
    result = run_assertion("exact text", Assertion(exact="exact text"))
    assert result.passed


def test_exact_fail() -> None:
    result = run_assertion("different text", Assertion(exact="exact text"))
    assert not result.passed


def test_json_schema_pass() -> None:
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    result = run_assertion('{"name": "agenci"}', Assertion(json_schema=schema))
    assert result.passed


def test_json_schema_fail_invalid_json() -> None:
    schema = {"type": "object"}
    result = run_assertion("not json", Assertion(json_schema=schema))
    assert not result.passed
    assert "not valid JSON" in result.detail


def test_json_schema_fail_schema_violation() -> None:
    schema = {"type": "object", "required": ["name"]}
    result = run_assertion("{}", Assertion(json_schema=schema))
    assert not result.passed


def test_custom_python_assertion(tmp_path, monkeypatch) -> None:
    module_file = tmp_path / "custom_checks.py"
    module_file.write_text("def is_uppercase(output):\n    return output.isupper(), 'must be uppercase'\n")
    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        result = run_assertion("HELLO", Assertion(custom_python="custom_checks:is_uppercase"))
        assert result.passed

        result_fail = run_assertion("hello", Assertion(custom_python="custom_checks:is_uppercase"))
        assert not result_fail.passed
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("custom_checks", None)
