"""Rule-ordered engineering failure taxonomy suggestion (019)."""

from __future__ import annotations

import re

from evaluation.generation.comparison_gt import _CROSS_VERB
from evaluation.generation.review.queue import assign_priority_tier
from models.benchmark_generation import AnswerType, FailureClass, GeneratedBenchmarkItem
from models.evaluation import BenchmarkResult
from models.investigation import EngineeringFailureClass, MaterializationAudit

ENGINEERING_TO_HUMAN_CLASS: dict[EngineeringFailureClass, FailureClass] = {
    EngineeringFailureClass.BINDING_ERROR: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.RETRIEVAL_LABEL_MISMATCH: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.SYNTHESIS_TEMPLATE_DUMP: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.NUMERIC_XBRL_MISS: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.COMPARISON_NARRATIVE_MISS: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.ABSTENTION: FailureClass.AGENT_FAILURE,
    EngineeringFailureClass.GT_ISSUE_SUSPECTED: FailureClass.GT_TOO_STRICT,
}

_BINDING_RE = re.compile(
    r"(wrong (company|filing|form)|10-K.*10-Q|incorrect (entity|issuer))",
    re.I,
)
_NUMERIC_RE = re.compile(r"[\d,]+\.?\d*")
_SCALE_HINT_RE = re.compile(r"\b(billion|million|trillion|B|M|T)\b", re.I)


def default_human_class(engineering: EngineeringFailureClass | None) -> FailureClass | None:
    if engineering is None:
        return None
    return ENGINEERING_TO_HUMAN_CLASS.get(engineering)


def rollup_engineering_counts(
    classes: list[EngineeringFailureClass | None],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cls in classes:
        if cls is None:
            key = "unclassified"
        else:
            key = cls.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def rollup_human_counts_from_engineering(
    classes: list[EngineeringFailureClass | None],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cls in classes:
        human = default_human_class(cls)
        if human is None:
            continue
        key = human.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _synthesis_path(result: BenchmarkResult | None) -> str:
    if result is None or not result.trajectory_snapshot:
        return ""
    snap = result.trajectory_snapshot
    if isinstance(snap, dict):
        return str(snap.get("synthesis_path") or "")
    return ""


def _answer_text(result: BenchmarkResult | None) -> str:
    if result is None or result.answer is None:
        return ""
    return (result.answer.text or "").strip()


def _judge_scores(result: BenchmarkResult | None) -> dict[str, float]:
    if result is None or result.judge_verdict is None:
        return {}
    scores = result.judge_verdict.scores or {}
    legacy = result.judge_verdict.legacy_scores
    merged = dict(scores)
    for key, val in legacy.items():
        merged.setdefault(key, val)
    return {k: float(v) for k, v in merged.items()}


def _outcome(result: BenchmarkResult | None) -> float:
    if result is None:
        return 0.0
    return float(result.outcome_score or 0.0)


def _mrr(result: BenchmarkResult | None) -> float:
    if result is None or result.ranking_metrics is None or result.ranking_metrics.mrr is None:
        return 0.0
    return float(result.ranking_metrics.mrr)


def _is_comparison_item(item: GeneratedBenchmarkItem | None) -> bool:
    if item is None:
        return False
    tag = (item.question_type_tag or "").lower()
    if "comparison" in tag:
        return True
    gt = item.ground_truth
    return bool(gt.required_claims) or gt.answer_type == AnswerType.COMPARISON_STRUCTURED


def _is_numeric_gt(item: GeneratedBenchmarkItem | None) -> bool:
    if item is None:
        return False
    if item.ground_truth.answer_type == AnswerType.NUMERIC:
        return True
    answer = (item.ground_truth.answer or "").strip()
    return bool(_NUMERIC_RE.search(answer))


def _answer_has_numeric_magnitude(answer: str, gt_answer: str) -> bool:
    ans_nums = _NUMERIC_RE.findall(answer.replace(",", ""))
    gt_nums = _NUMERIC_RE.findall(gt_answer.replace(",", ""))
    if not ans_nums or not gt_nums:
        return False
    try:
        ans_val = float(ans_nums[0])
        gt_val = float(gt_nums[0])
    except ValueError:
        return False
    if gt_val == 0:
        return ans_val == 0
    ratio = abs(ans_val / gt_val)
    return 0.05 <= ratio <= 20.0


def _gt_scale_anomaly(item: GeneratedBenchmarkItem | None, answer: str) -> bool:
    if item is None:
        return False
    gt = (item.ground_truth.answer or "").strip()
    question = (item.question or "").lower()
    gt_has_scale = bool(_SCALE_HINT_RE.search(gt))
    q_has_scale = bool(_SCALE_HINT_RE.search(question))
    ans_has_scale = bool(_SCALE_HINT_RE.search(answer))
    if q_has_scale and not gt_has_scale and _answer_has_numeric_magnitude(answer, gt):
        return True
    if gt_has_scale and not ans_has_scale and _NUMERIC_RE.search(answer):
        return True
    return False


def suggest_failure_class(
    *,
    item: GeneratedBenchmarkItem | None,
    result: BenchmarkResult | None,
    materialization_audit: MaterializationAudit | None = None,
) -> tuple[EngineeringFailureClass | None, str]:
    answer = _answer_text(result)
    outcome = _outcome(result)
    synthesis_path = _synthesis_path(result)
    scores = _judge_scores(result)
    rationale = ""
    if result and result.judge_verdict:
        rationale = (result.judge_verdict.rationale or "").strip()

    # 1. abstention
    if not answer or re.search(
        r"\b(insufficient evidence|cannot determine|not available in)\b",
        answer,
        re.I,
    ):
        if not _answer_has_numeric_magnitude(answer, (item.ground_truth.answer if item else "") or ""):
            return EngineeringFailureClass.ABSTENTION, "empty or insufficient-evidence answer"

    # 2. binding_error
    if materialization_audit and materialization_audit.binding_miss:
        return EngineeringFailureClass.BINDING_ERROR, "expected sections not visited (binding_miss)"
    if _BINDING_RE.search(rationale):
        return EngineeringFailureClass.BINDING_ERROR, "judge rationale cites binding mismatch"

    # 3. synthesis_template_dump
    if answer.startswith("Based on") and "evidence chunk" in answer.lower():
        if synthesis_path in ("template", "live_llm", "") and outcome <= 0:
            return EngineeringFailureClass.SYNTHESIS_TEMPLATE_DUMP, "template-style evidence list answer"

    # 4. numeric_xbrl_miss
    if item and _is_numeric_gt(item) and _mrr(result) >= 0.5:
        paths = item.expected_section_paths or []
        if any("XBRL" in p.upper() for p in paths):
            gt_answer = (item.ground_truth.answer or "").strip()
            if not _answer_has_numeric_magnitude(answer, gt_answer):
                return EngineeringFailureClass.NUMERIC_XBRL_MISS, "numeric GT with XBRL paths but ungrounded answer"

    # 5. comparison_narrative_miss
    if item and _is_comparison_item(item) and outcome <= 0:
        if not _CROSS_VERB.search(answer):
            return EngineeringFailureClass.COMPARISON_NARRATIVE_MISS, "comparison item lacks cross-filing contrast"

    # 6. retrieval_label_mismatch
    if _mrr(result) >= 0.5 and scores.get("retrieval_fidelity", 1.0) == 0.0:
        return EngineeringFailureClass.RETRIEVAL_LABEL_MISMATCH, "high MRR with retrieval_fidelity=0"

    # 7. gt_issue_suspected
    if _mrr(result) >= 0.5 and outcome <= 0 and item:
        if _NUMERIC_RE.search(answer) and _gt_scale_anomaly(item, answer):
            return EngineeringFailureClass.GT_ISSUE_SUSPECTED, "numeric answer present but GT scale heuristic mismatch"

    return None, "unclassified"


def is_strong_retrieval_zero_outcome(
    *,
    outcome_score: float | None,
    mrr: float | None,
    ndcg_at_10: float | None,
) -> bool:
    tier, _ = assign_priority_tier(
        outcome_score=outcome_score,
        mrr=mrr,
        ndcg_at_10=ndcg_at_10,
    )
    return tier == 1


def extract_weakest_judge_criterion(result: BenchmarkResult | None) -> str:
    scores = _judge_scores(result)
    if not scores:
        return "value_alignment"
    filtered = {k: v for k, v in scores.items() if k not in {"trajectory_fidelity"}}
    if not filtered:
        filtered = scores
    return min(filtered.items(), key=lambda kv: kv[1])[0]
