"""Quality-pass summary aggregation after review and selective re-judge (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import latest_annotations_by_item
from evaluation.generation.review.overrides import _load_changelog
from evaluation.generation.review.queue import assign_priority_tier, build_review_queue
from models.benchmark_generation import FailureClass, QualityPassSummary


def build_quality_pass_summary(
    bundle_root: Path,
    *,
    repro_input: Path | None = None,
    baseline_repro_input: Path | None = None,
    variant: str = "graph-full",
) -> QualityPassSummary:
    latest = latest_annotations_by_item(bundle_root)
    changelog = _load_changelog(bundle_root)

    failure_counts: dict[str, int] = {}
    for ann in latest.values():
        key = ann.failure_class.value
        failure_counts[key] = failure_counts.get(key, 0) + 1

    fixed_override = sum(1 for entry in changelog if entry.validation_outcome == "accepted")
    fixed_regenerate = sum(
        1
        for entry in changelog
        if entry.validation_outcome == "accepted" and "regenerate" in (entry.rationale or "").lower()
    )

    queue = build_review_queue(
        bundle_root,
        repro_input=repro_input or baseline_repro_input,
        variant=variant,
    )
    dataset_caused = 0
    for entry in queue:
        if entry.outcome_score is None or float(entry.outcome_score) > 0:
            continue
        tier, _ = assign_priority_tier(
            outcome_score=entry.outcome_score,
            mrr=entry.mrr,
            ndcg_at_10=entry.ndcg_at_10,
        )
        if tier != 1:
            continue
        ann = latest.get(entry.item_id)
        if ann is None or ann.failure_class == FailureClass.AGENT_FAILURE:
            continue
        dataset_caused += 1

    tier1_total = sum(1 for e in queue if e.priority_tier == 1)
    dataset_rate = dataset_caused / tier1_total if tier1_total else 0.0

    improved = 0
    compared = 0
    if baseline_repro_input and repro_input and baseline_repro_input != repro_input:
        improved, compared = _rejudge_delta(
            baseline_repro_input,
            repro_input,
            variant,
            {entry.item_id for entry in changelog if entry.validation_outcome == "accepted"},
        )

    return QualityPassSummary(
        items_reviewed=len(latest),
        items_fixed_override=fixed_override,
        items_fixed_regenerate=fixed_regenerate,
        failure_class_counts=failure_counts,
        dataset_caused_zero_score_count=dataset_caused,
        dataset_caused_zero_score_rate=dataset_rate,
        rejudge_improved_count=improved,
        rejudge_improved_rate=improved / compared if compared else 0.0,
    )


def _rejudge_delta(
    baseline: Path,
    updated: Path,
    variant: str,
    item_ids: set[str],
) -> tuple[int, int]:
    from evaluation.generation.review.queue import _load_repro_results, _outcome_score

    before = _load_repro_results(baseline, variant)
    after = _load_repro_results(updated, variant)
    improved = 0
    compared = 0
    for item_id in item_ids:
        b = before.get(item_id)
        a = after.get(item_id)
        if b is None or a is None:
            continue
        compared += 1
        if _outcome_score(a) > _outcome_score(b):
            improved += 1
    return improved, compared


def write_quality_pass_summary(bundle_root: Path, summary: QualityPassSummary) -> Path:
    path = bundle_root / "quality_pass_summary.json"
    path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
