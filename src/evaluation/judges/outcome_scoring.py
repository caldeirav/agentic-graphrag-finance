"""Composite outcome and alignment scores from judge verdicts (P0 eval fixes)."""

from __future__ import annotations

from models.enums import Sufficiency
from models.evaluation import BenchmarkItem, JudgeVerdict
from models.query import AnswerPackage

ABSTENTION_PREFIX = "insufficient evidence"


def is_abstention_answer(answer: AnswerPackage | None) -> bool:
    """True when the agent declined to answer or returned no grounded citations."""
    if answer is None:
        return True
    if answer.sufficiency == Sufficiency.INSUFFICIENT:
        return True
    text = (answer.text or "").strip().lower()
    if not text:
        return True
    if text.startswith(ABSTENTION_PREFIX):
        return True
    return "insufficient evidence" in text and not (answer.citations or [])


def criteria_for_item(item: BenchmarkItem) -> tuple[str, ...]:
    """Judge criteria required for this benchmark item."""
    ids = [
        "trajectory_coherence",
        "routing_decisions",
        "retrieval_fidelity",
        "synthesis_grounding",
    ]
    gt = item.ground_truth
    if gt and gt.answer:
        ids.append("value_alignment")
    if gt and gt.rubric:
        ids.append("claim_presence")
    return tuple(ids)


def compute_outcome_scores(
    item: BenchmarkItem,
    answer: AnswerPackage | None,
    verdict: JudgeVerdict,
) -> tuple[float, float]:
    """Map judge verdict + item GT to headline outcome_accuracy and rubric_alignment."""
    scores = verdict.scores
    gt = item.ground_truth
    has_answer_gt = bool(gt and gt.answer)
    has_rubric_gt = bool(gt and gt.rubric)

    alignment = float(scores.get("claim_presence", 0.0)) if has_rubric_gt else 0.0

    if is_abstention_answer(answer):
        if has_answer_gt or has_rubric_gt:
            return 0.0, 0.0 if has_rubric_gt else alignment
        return float(scores.get("synthesis_grounding", 0.0)), alignment

    if has_answer_gt:
        outcome = scores.get("value_alignment", scores.get("synthesis_grounding", 0.0))
    else:
        outcome = scores.get("synthesis_grounding", 0.0)

    return float(outcome), alignment
