"""Load investigation inputs from review queue, repro results, and draft bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.queue import _load_repro_results, _outcome_score, _ranking_values
from models.benchmark_generation import GeneratedBenchmarkItem, ReviewQueueEntry
from models.evaluation import BenchmarkResult


@dataclass
class InvestigationInputs:
    bundle_root: Path
    item_ids: list[str]
    items_by_id: dict[str, GeneratedBenchmarkItem]
    repro_by_id: dict[str, BenchmarkResult]
    queue_by_id: dict[str, ReviewQueueEntry]
    repro_results_path: Path | None
    variant: str


def load_review_queue_entries(queue_path: Path) -> list[ReviewQueueEntry]:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [ReviewQueueEntry.model_validate(row) for row in payload]
    entries = payload.get("entries")
    if isinstance(entries, list):
        return [ReviewQueueEntry.model_validate(row) for row in entries]
    item_ids = payload.get("item_ids")
    if isinstance(item_ids, list):
        return [
            ReviewQueueEntry(item_id=str(iid), priority_tier=1, priority_score=0.0) for iid in item_ids
        ]
    msg = f"Unsupported review queue format: {queue_path}"
    raise ValueError(msg)


def resolve_item_ids(
    *,
    queue_file: Path | None,
    item_ids_file: Path | None,
    tier_filter: int | None = 1,
) -> list[str]:
    if item_ids_file is not None:
        payload = json.loads(item_ids_file.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [str(i) for i in payload]
        if isinstance(payload.get("item_ids"), list):
            return [str(i) for i in payload["item_ids"]]
        entries = payload.get("entries")
        if isinstance(entries, list):
            ids = [str(e["item_id"]) for e in entries if "item_id" in e]
            if tier_filter is None:
                return ids
            return [
                str(e["item_id"])
                for e in entries
                if e.get("priority_tier", 1) == tier_filter
            ]
    if queue_file is not None:
        entries = load_review_queue_entries(queue_file)
        if tier_filter is None:
            return [e.item_id for e in entries]
        return [e.item_id for e in entries if e.priority_tier == tier_filter]
    msg = "Provide --queue-file or --item-ids-file"
    raise ValueError(msg)


def load_investigation_inputs(
    draft: Path,
    *,
    repro_input: Path | None,
    variant: str = "graph-full",
    item_ids: list[str] | None = None,
    queue_file: Path | None = None,
) -> InvestigationInputs:
    bundle_root = resolve_draft_bundle(draft)
    items = {item.item_id: item for item in load_dev_split_items(bundle_root / "items" / "dev.jsonl")}

    if item_ids is None and queue_file is not None:
        item_ids = resolve_item_ids(queue_file=queue_file, item_ids_file=None)

    queue_by_id: dict[str, ReviewQueueEntry] = {}
    if queue_file is not None:
        for entry in load_review_queue_entries(queue_file):
            queue_by_id[entry.item_id] = entry

    if item_ids is None:
        item_ids = list(items.keys())

    repro_by_id: dict[str, BenchmarkResult] = {}
    repro_results_path: Path | None = None
    if repro_input is not None:
        repro_results_path = repro_input / variant / "results.json"
        repro_by_id = _load_repro_results(repro_input, variant)

    return InvestigationInputs(
        bundle_root=bundle_root,
        item_ids=item_ids,
        items_by_id=items,
        repro_by_id=repro_by_id,
        queue_by_id=queue_by_id,
        repro_results_path=repro_results_path,
        variant=variant,
    )


def outcome_and_ranking(result: BenchmarkResult | None) -> tuple[float | None, float | None, float | None]:
    if result is None:
        return None, None, None
    mrr, ndcg = _ranking_values(result)
    return _outcome_score(result), mrr, ndcg
