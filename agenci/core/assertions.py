"""Implementations of the functional assertion types.

Each ``check_*`` function takes the agent output plus the Assertion and
returns an AssertionResult. ``run_assertion`` dispatches on assertion
type. Custom Python assertions are loaded via ``module.path:function``
and must accept a single string argument (the output) and return either
a bool or a (bool, str) tuple.
"""

from __future__ import annotations

import importlib
import json
import re

import jsonschema

from agenci.core.models import Assertion, AssertionResult, AssertionType


def check_contains(output: str, expected: str) -> AssertionResult:
    passed = expected in (output or "")
    return AssertionResult(
        assertion=f"contains: {expected!r}",
        passed=passed,
        detail="" if passed else f"Output did not contain {expected!r}",
    )


def check_not_contains(output: str, forbidden: str) -> AssertionResult:
    passed = forbidden not in (output or "")
    return AssertionResult(
        assertion=f"not_contains: {forbidden!r}",
        passed=passed,
        detail="" if passed else f"Output unexpectedly contained {forbidden!r}",
    )


def check_regex(output: str, pattern: str) -> AssertionResult:
    passed = re.search(pattern, output or "") is not None
    return AssertionResult(
        assertion=f"regex: {pattern!r}",
        passed=passed,
        detail="" if passed else f"Output did not match /{pattern}/",
    )


def check_exact(output: str, expected: str) -> AssertionResult:
    passed = (output or "") == expected
    return AssertionResult(
        assertion="exact match",
        passed=passed,
        detail="" if passed else f"Expected exact match with {expected!r}",
    )


def check_json_schema(output: str, schema: dict) -> AssertionResult:
    try:
        parsed = json.loads(output or "")
    except json.JSONDecodeError as exc:
        return AssertionResult(
            assertion="json_schema", passed=False, detail=f"Output is not valid JSON: {exc}"
        )
    try:
        jsonschema.validate(parsed, schema)
    except jsonschema.ValidationError as exc:
        return AssertionResult(
            assertion="json_schema", passed=False, detail=f"Schema violation: {exc.message}"
        )
    return AssertionResult(assertion="json_schema", passed=True)


def check_custom_python(output: str, dotted_path: str) -> AssertionResult:
    module_path, _, func_name = dotted_path.partition(":")
    if not func_name:
        return AssertionResult(
            assertion=f"custom_python: {dotted_path}",
            passed=False,
            detail="custom_python must be in 'module.path:function_name' form",
        )
    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except (ImportError, AttributeError) as exc:
        return AssertionResult(
            assertion=f"custom_python: {dotted_path}",
            passed=False,
            detail=f"Could not load assertion function: {exc}",
        )

    result = func(output)
    if isinstance(result, tuple):
        passed, detail = result
    else:
        passed, detail = bool(result), ""
    return AssertionResult(assertion=f"custom_python: {dotted_path}", passed=passed, detail=detail)


def run_assertion(output: str, assertion: Assertion) -> AssertionResult:
    kind = assertion.assertion_type()
    if kind is AssertionType.CONTAINS:
        return check_contains(output, assertion.contains)  # type: ignore[arg-type]
    if kind is AssertionType.NOT_CONTAINS:
        return check_not_contains(output, assertion.not_contains)  # type: ignore[arg-type]
    if kind is AssertionType.REGEX:
        return check_regex(output, assertion.regex)  # type: ignore[arg-type]
    if kind is AssertionType.EXACT:
        return check_exact(output, assertion.exact)  # type: ignore[arg-type]
    if kind is AssertionType.JSON_SCHEMA:
        return check_json_schema(output, assertion.json_schema)  # type: ignore[arg-type]
    if kind is AssertionType.CUSTOM_PYTHON:
        return check_custom_python(output, assertion.custom_python)  # type: ignore[arg-type]
    if kind is AssertionType.SEMANTIC_SIMILARITY:
        # Handled by the evaluator layer (requires a judge/embedding provider).
        raise NotImplementedError(
            "semantic_similarity assertions are resolved via the evaluator, not run_assertion"
        )
    raise ValueError(f"Unhandled assertion type: {kind}")
