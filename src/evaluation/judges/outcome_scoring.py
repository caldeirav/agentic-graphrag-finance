"""Composite outcome and alignment scores from judge verdicts (P0 eval fixes)."""

from __future__ import annotations

import re

from models.enums import Sufficiency
from models.evaluation import BenchmarkItem, JudgeVerdict
from models.query import AnswerPackage

ABSTENTION_PREFIX = "insufficient evidence"

GRAPH_VARIANTS = frozenset(
    {
        "graph-full",
        "ablation-no-macro",
        "ablation-no-walker",
        "ablation-xbrl-only",
    }
)
FLAT_VARIANT = "flat-chunk"
MIN_JUDGE_VERSION = 3.1


def _judge_version_number(version: str) -> float:
    raw = (version or "").strip().lower()
    match = re.match(r"v?(\d+)(?:\.(\d+))?", raw)
    if not match:
        return 0.0
    minor = int(match.group(2) or 0)
    return float(f"{int(match.group(1))}.{minor}")


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


def base_criteria(variant_id: str) -> tuple[str, ...]:
    if variant_id == FLAT_VARIANT:
        return ("retrieval_fidelity", "answer_quality", "synthesis_grounding")
    return (
        "trajectory_coherence",
        "routing_decisions",
        "retrieval_fidelity",
        "synthesis_grounding",
    )


def criteria_for_item(item: BenchmarkItem, variant_id: str = "graph-full") -> tuple[str, ...]:
    """Judge criteria required for this benchmark item and reproduction variant."""
    ids = list(base_criteria(variant_id))
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
        outcome = float(scores.get("value_alignment", 0.0))
    else:
        outcome = scores.get("synthesis_grounding", 0.0)

    return float(outcome), alignment


def should_skip_judging(
    existing: JudgeVerdict | None,
    item: BenchmarkItem,
    variant_id: str,
    *,
    force_rescore: bool = False,
) -> bool:
    """True when an existing v3+ verdict has every criterion required for this item/variant."""
    if force_rescore or existing is None:
        return False
    if _judge_version_number(existing.judge_version or "") < MIN_JUDGE_VERSION:
        return False
    required = set(criteria_for_item(item, variant_id))
    return required <= set(existing.scores.keys())
