"""Gold-path benchmark gate (009)."""

from __future__ import annotations

import os

import pytest

from cli.gold_path_eval import run_gold_path_eval


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
def test_gold_path_benchmark_passes_on_fixture_slice():
    report = run_gold_path_eval()
    assert report["total"] >= 40
    assert report["passed"]
