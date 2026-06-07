"""Unit tests for variant-aware judge criteria (016)."""

import os

from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.judges.outcome_scoring import criteria_for_item
from models.evaluation import BenchmarkItem, GroundTruth


def test_graph_full_includes_trajectory_criteria() -> None:
    item = BenchmarkItem(item_id="i1", dataset="custom-judge", question="q")
    ids = criteria_for_item(item, "graph-full")
    assert "trajectory_coherence" in ids
    assert "routing_decisions" in ids
    assert "answer_quality" not in ids


def test_flat_chunk_retrieval_focused_criteria() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    ids = criteria_for_item(item, "flat-chunk")
    assert ids == (
        "retrieval_fidelity",
        "answer_quality",
        "synthesis_grounding",
        "value_alignment",
    )
    assert "trajectory_coherence" not in ids
    assert "routing_decisions" not in ids


def test_mock_judge_flat_chunk_excludes_trajectory_scores() -> None:
    os.environ["USE_MOCK_JUDGE"] = "1"
    panel = GeminiJudgePanel()
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    verdict = panel.judge(item, None, None, variant_id="flat-chunk")
    assert verdict.judge_version == "v3"
    assert "trajectory_coherence" not in verdict.scores
    assert "routing_decisions" not in verdict.scores
    assert "answer_quality" in verdict.scores
