"""Unit tests for fair outcome scoring policy (016)."""

from evaluation.judges.outcome_scoring import compute_outcome_scores
from models.evaluation import BenchmarkItem, GroundTruth, JudgeVerdict
from models.query import AnswerPackage, EvidenceChunk


def test_answer_gt_uses_value_alignment_only() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    answer = AnswerPackage(
        text="The answer is 42.",
        citations=[EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h")],
    )
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={"synthesis_grounding": 1.0, "value_alignment": 0.25},
    )
    outcome, _ = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.25


def test_missing_value_alignment_scores_zero() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    answer = AnswerPackage(
        text="chunk dump",
        citations=[EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h")],
    )
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={"synthesis_grounding": 1.0},
    )
    outcome, _ = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.0


def test_rubric_gt_excluded_from_outcome() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(rubric="must cite risk factors"),
    )
    answer = AnswerPackage(
        text="Risk factors include ...",
        citations=[EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h")],
    )
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={"synthesis_grounding": 0.9, "claim_presence": 0.8},
    )
    outcome, alignment = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.9
    assert alignment == 0.8


def test_synthesis_fallback_does_not_inflate_answer_gt_outcome() -> None:
    """SC-005: high synthesis with zero VA must not yield high outcome on answer-GT."""
    item = BenchmarkItem(
        item_id="html-dump",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="391035"),
    )
    answer = AnswerPackage(
        text=" ".join(["chunk excerpt"] * 40),
        citations=[EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h")],
    )
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v3",
        scores={"synthesis_grounding": 1.0, "value_alignment": 0.0},
    )
    outcome, _ = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.0
