"""Unit tests for judge-batch v3 resume gate (016)."""

from evaluation.reproduction import judge_batch as jb
from models.evaluation import BenchmarkItem, BenchmarkResult, GroundTruth, JudgeVerdict


def _item() -> BenchmarkItem:
    return BenchmarkItem(
        item_id="item-1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )


def _result(
    *,
    judge_version: str = "v2",
    scores: dict[str, float] | None = None,
    status: str = "ok",
) -> BenchmarkResult:
    return BenchmarkResult(
        item_id="item-1",
        judge_status=status,
        judge_verdict=JudgeVerdict(
            judge_model="gemini",
            judge_version=judge_version,
            scores=scores or {},
        ),
        trajectory_snapshot={"evidence_chunks": [{"chunk_node_id": "doc-html-a"}]},
    )


def test_skip_v3_with_complete_criteria() -> None:
    rows = [
        _result(
            judge_version="v3",
            scores={
                "trajectory_coherence": 1.0,
                "routing_decisions": 1.0,
                "retrieval_fidelity": 1.0,
                "synthesis_grounding": 1.0,
                "value_alignment": 1.0,
            },
        )
    ]
    pending, missing = jb._pending_results(rows, {"item-1": _item()}, "graph-full", force_rescore=False)
    assert pending == []
    assert missing == 0


def test_no_skip_v2_partial_criteria() -> None:
    rows = [
        _result(
            judge_version="v2",
            scores={
                "trajectory_coherence": 1.0,
                "routing_decisions": 1.0,
                "retrieval_fidelity": 1.0,
                "synthesis_grounding": 1.0,
            },
        )
    ]
    pending, missing = jb._pending_results(rows, {"item-1": _item()}, "graph-full", force_rescore=False)
    assert pending == rows
    assert missing == 0


def test_no_skip_v3_missing_value_alignment() -> None:
    rows = [
        _result(
            judge_version="v3",
            scores={
                "trajectory_coherence": 1.0,
                "routing_decisions": 1.0,
                "retrieval_fidelity": 1.0,
                "synthesis_grounding": 1.0,
            },
        )
    ]
    pending, missing = jb._pending_results(rows, {"item-1": _item()}, "graph-full", force_rescore=False)
    assert pending == rows
    assert missing == 0


def test_force_rescore_includes_v3_complete() -> None:
    rows = [
        _result(
            judge_version="v3",
            scores={
                "trajectory_coherence": 1.0,
                "routing_decisions": 1.0,
                "retrieval_fidelity": 1.0,
                "synthesis_grounding": 1.0,
                "value_alignment": 1.0,
            },
        )
    ]
    pending, missing = jb._pending_results(rows, {"item-1": _item()}, "graph-full", force_rescore=True)
    assert pending == rows
    assert missing == 0


def test_checkpoint_item_missing_from_bundle_not_pending_even_with_force_rescore() -> None:
    rows = [_result(judge_version="v2")]
    pending, missing = jb._pending_results(rows, {}, "graph-full", force_rescore=True)
    assert pending == []
    assert missing == 1
