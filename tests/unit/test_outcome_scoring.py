"""Unit tests for composite outcome scoring (P0 eval fixes)."""

from evaluation.judges.outcome_scoring import (
    compute_outcome_scores,
    criteria_for_item,
    is_abstention_answer,
)
from models.enums import Sufficiency
from models.evaluation import BenchmarkItem, GroundTruth, JudgeVerdict
from models.query import AnswerPackage, EvidenceChunk


def test_is_abstention_detects_insufficient_evidence_text() -> None:
    answer = AnswerPackage(
        text="Insufficient evidence in the ingested corpus to answer this question.",
        citations=[],
        sufficiency=Sufficiency.INSUFFICIENT,
    )
    assert is_abstention_answer(answer) is True


def test_abstention_penalized_when_answer_ground_truth_exists() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    answer = AnswerPackage(
        text="Insufficient evidence in the ingested corpus to answer this question.",
        citations=[],
        sufficiency=Sufficiency.INSUFFICIENT,
    )
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v",
        scores={"synthesis_grounding": 1.0, "value_alignment": 0.95},
    )
    outcome, alignment = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.0


def test_outcome_prefers_value_alignment_when_answer_gt_exists() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="42"),
    )
    answer = AnswerPackage(text="Revenue was 42 million.", citations=[EvidenceChunk(
        chunk_node_id="c1", excerpt="x", content_hash="h"
    )])
    verdict = JudgeVerdict(
        judge_model="m",
        judge_version="v",
        scores={"synthesis_grounding": 0.4, "value_alignment": 0.9},
    )
    outcome, _ = compute_outcome_scores(item, answer, verdict)
    assert outcome == 0.9


def test_criteria_for_item_includes_gt_rubrics() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="a", rubric="must mention risk"),
    )
    ids = criteria_for_item(item)
    assert "value_alignment" in ids
    assert "claim_presence" in ids
    assert len(ids) == 6
