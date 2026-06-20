"""Reproduction-driven review queue export (018)."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.annotations import latest_annotations_by_item
from models.benchmark_generation import ReviewQueueEntry
from models.evaluation import BenchmarkResult


def _outcome_score(row: BenchmarkResult) -> float:
    if row.outcome_score is not None:
        return float(row.outcome_score)
    verdict = row.judge_verdict
    if verdict is None:
        return 0.0
    scores = verdict.legacy_scores if hasattr(verdict, "legacy_scores") else verdict.scores
    return float(scores.get("value_alignment", 0.0) or 0.0)


def _ranking_values(row: BenchmarkResult) -> tuple[float | None, float | None]:
    if row.ranking_metrics is None:
        return None, None
    mrr = row.ranking_metrics.mrr
    ndcg = row.ranking_metrics.ndcg_at_10
    return (float(mrr) if mrr is not None else None, float(ndcg) if ndcg is not None else None)


def assign_priority_tier(
    *,
    outcome_score: float | None,
    mrr: float | None,
    ndcg_at_10: float | None,
) -> tuple[int, float]:
    """Return (tier, priority_score) per review-queue-export contract."""
    if outcome_score is None:
        return 3, 0.0
    outcome = float(outcome_score)
    if outcome > 0:
        return 3, 0.0
    mrr_val = mrr or 0.0
    ndcg_val = ndcg_at_10 or 0.0
    if mrr_val >= 0.5 or ndcg_val >= 0.3:
        return 1, max(mrr_val, ndcg_val)
    return 2, 0.1


def _load_repro_results(repro_input: Path, variant: str) -> dict[str, BenchmarkResult]:
    results_path = repro_input / variant / "results.json"
    if not results_path.is_file():
        return {}
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    return {row["item_id"]: BenchmarkResult.model_validate(row) for row in rows}


def build_review_queue(
    bundle_root: Path,
    *,
    repro_input: Path | None = None,
    variant: str = "graph-full",
    tier_filter: int | None = None,
    exclude_failure_classes: set[str] | None = None,
    max_items: int | None = None,
) -> list[ReviewQueueEntry]:
    root = resolve_draft_bundle(bundle_root)
    items = load_dev_split_items(root / "items" / "dev.jsonl")
    repro_by_id = _load_repro_results(repro_input, variant) if repro_input else {}
    latest_ann = latest_annotations_by_item(root)

    entries: list[ReviewQueueEntry] = []
    for item in items:
        failure_class = None
        ann = latest_ann.get(item.item_id)
        if ann is not None:
            failure_class = ann.failure_class.value
            if exclude_failure_classes and failure_class in exclude_failure_classes:
                continue

        repro_row = repro_by_id.get(item.item_id)
        mrr: float | None = None
        ndcg: float | None = None
        outcome: float | None = None
        if repro_row is not None:
            mrr, ndcg = _ranking_values(repro_row)
            outcome = _outcome_score(repro_row)

        tier, score = assign_priority_tier(
            outcome_score=outcome,
            mrr=mrr,
            ndcg_at_10=ndcg,
        )
        if tier_filter is not None and tier != tier_filter:
            continue

        entries.append(
            ReviewQueueEntry(
                item_id=item.item_id,
                priority_tier=tier,
                priority_score=score,
                mrr=mrr,
                ndcg_at_10=ndcg,
                outcome_score=outcome,
                inspiration_profile=item.inspiration_profile,
                question_preview=item.question[:120],
                latest_failure_class=failure_class,
            )
        )

    entries.sort(key=lambda e: (e.priority_tier, -e.priority_score, e.item_id))
    if max_items is not None:
        entries = entries[:max_items]
    return entries


def write_review_queue(
    bundle_root: Path,
    entries: list[ReviewQueueEntry],
    output_basename: Path,
    *,
    repro_input: Path | None = None,
    variant: str = "graph-full",
) -> tuple[Path, Path]:
    root = resolve_draft_bundle(bundle_root)
    manifest_path = root / "manifest.json"
    bundle_version = "unknown"
    if manifest_path.is_file():
        bundle_version = json.loads(manifest_path.read_text(encoding="utf-8")).get("version", bundle_version)

    tier_counts: dict[str, int] = {"1": 0, "2": 0, "3": 0}
    for entry in entries:
        tier_counts[str(entry.priority_tier)] = tier_counts.get(str(entry.priority_tier), 0) + 1

    envelope = {
        "exported_at": datetime.now(UTC).isoformat(),
        "bundle_version": bundle_version,
        "repro_input": str(repro_input) if repro_input else None,
        "baseline_variant": variant,
        "tier_counts": tier_counts,
        "entries": [e.model_dump(mode="json") for e in entries],
    }
    json_path = output_basename.with_suffix(".json")
    csv_path = output_basename.with_suffix(".csv")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fieldnames = [
        "item_id",
        "priority_tier",
        "priority_score",
        "mrr",
        "ndcg_at_10",
        "outcome_score",
        "inspiration_profile",
        "question_preview",
        "latest_failure_class",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "item_id": entry.item_id,
                    "priority_tier": entry.priority_tier,
                    "priority_score": entry.priority_score,
                    "mrr": entry.mrr if entry.mrr is not None else "",
                    "ndcg_at_10": entry.ndcg_at_10 if entry.ndcg_at_10 is not None else "",
                    "outcome_score": entry.outcome_score if entry.outcome_score is not None else "",
                    "inspiration_profile": entry.inspiration_profile,
                    "question_preview": entry.question_preview,
                    "latest_failure_class": entry.latest_failure_class or "",
                }
            )
    return json_path, csv_path
