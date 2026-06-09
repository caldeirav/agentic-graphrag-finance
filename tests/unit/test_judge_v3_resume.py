"""Unit tests for judge v3 resume gate (016)."""

from evaluation.judges.outcome_scoring import should_skip_judging
from models.evaluation import BenchmarkItem, GroundTruth, JudgeVerdict


def _item(*, answer: str | None = "42", rubric: str | None = None) -> BenchmarkItem:
    return BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer=answer, rubric=rubric),
    )


def test_v2_never_skips() -> None:
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v2",
        scores={"trajectory_coherence": 1.0, "value_alignment": 1.0},
    )
    assert should_skip_judging(verdict, _item(), "graph-full") is False


def test_v3_complete_does_not_skip() -> None:
    """v3 scores must be re-judged under graded v3.1 rubric."""
    item = _item()
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={
            "trajectory_coherence": 1.0,
            "routing_decisions": 1.0,
            "retrieval_fidelity": 1.0,
            "synthesis_grounding": 1.0,
            "value_alignment": 1.0,
        },
    )
    assert should_skip_judging(verdict, item, "graph-full") is False


def test_v3_1_complete_skips() -> None:
    item = _item()
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3.1",
        scores={
            "trajectory_coherence": 1.0,
            "routing_decisions": 1.0,
            "retrieval_fidelity": 1.0,
            "synthesis_grounding": 1.0,
            "value_alignment": 1.0,
        },
    )
    assert should_skip_judging(verdict, item, "graph-full") is True


def test_v3_incomplete_criteria_does_not_skip() -> None:
    item = _item()
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={
            "trajectory_coherence": 1.0,
            "routing_decisions": 1.0,
            "retrieval_fidelity": 1.0,
            "synthesis_grounding": 1.0,
        },
    )
    assert should_skip_judging(verdict, item, "graph-full") is False


def test_force_rescore_never_skips() -> None:
    item = _item()
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={
            "trajectory_coherence": 1.0,
            "routing_decisions": 1.0,
            "retrieval_fidelity": 1.0,
            "synthesis_grounding": 1.0,
            "value_alignment": 1.0,
        },
    )
    assert should_skip_judging(verdict, item, "graph-full", force_rescore=True) is False
