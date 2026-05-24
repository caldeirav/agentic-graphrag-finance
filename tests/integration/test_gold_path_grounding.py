"""Gold-path grounding subset (009 SC-005)."""

from __future__ import annotations

import os

import pytest

from cli.gold_path_eval import run_gold_path_eval
from evaluation.metrics.gold_path import chunk_reach_rate


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
def test_gold_path_meets_reach_threshold():
    report = run_gold_path_eval()
    assert report["total"] >= 40
    assert report["chunk_reach_rate"] >= 0.75
    assert chunk_reach_rate([{"reached": True}] * 3 + [{"reached": False}]) == 0.75
