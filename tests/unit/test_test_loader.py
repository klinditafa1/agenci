from __future__ import annotations

from pathlib import Path

import pytest

from agenci.core.test_loader import TestLoadError, load_all_tests, load_test_file


def test_load_test_file_with_tests_key(tmp_path: Path) -> None:
    f = tmp_path / "t.yaml"
    f.write_text(
        """
tests:
  - name: case1
    input: "hello"
    assertions:
      - contains: "hi"
"""
    )
    cases = load_test_file(f)
    assert len(cases) == 1
    assert cases[0].name == "case1"


def test_load_test_file_top_level_list(tmp_path: Path) -> None:
    f = tmp_path / "t.yaml"
    f.write_text(
        """
- name: case1
  input: "hello"
"""
    )
    cases = load_test_file(f)
    assert len(cases) == 1


def test_load_test_file_single_mapping(tmp_path: Path) -> None:
    f = tmp_path / "t.yaml"
    f.write_text("name: case1\ninput: hello\n")
    cases = load_test_file(f)
    assert len(cases) == 1


def test_invalid_test_case_raises_readable_error(tmp_path: Path) -> None:
    f = tmp_path / "t.yaml"
    f.write_text("tests:\n  - name: case1\n")  # missing required 'input'
    with pytest.raises(TestLoadError) as exc_info:
        load_test_file(f)
    assert "input" in str(exc_info.value)


def test_load_all_tests_across_directories(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.yaml").write_text("tests:\n  - name: a\n    input: hi\n")
    (tmp_path / "tests" / "b.yml").write_text("tests:\n  - name: b\n    input: hi\n")
    cases = load_all_tests(["tests"], root=tmp_path)
    assert {c.name for c in cases} == {"a", "b"}


def test_load_all_tests_no_files_raises(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    with pytest.raises(TestLoadError):
        load_all_tests(["tests"], root=tmp_path)
