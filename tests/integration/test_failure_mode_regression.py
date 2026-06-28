"""Integration wrapper ensuring failure-mode regression directory is importable."""

from __future__ import annotations

from pathlib import Path


def test_failure_mode_regression_directory_exists() -> None:
    root = Path("tests/regression/failure_modes")
    assert root.is_dir()
    tests = list(root.glob("test_*.py"))
    assert len(tests) >= 4
