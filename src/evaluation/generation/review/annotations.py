"""Append-only annotation sidecar for dataset quality review (018)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    FailureClass,
    ItemAnnotation,
    ProposedOverrides,
    ReproContextSnapshot,
)


def annotations_path(bundle_root: Path) -> Path:
    return bundle_root / "annotations.jsonl"


def load_annotation_history(bundle_root: Path) -> list[ItemAnnotation]:
    path = annotations_path(bundle_root)
    if not path.is_file():
        return []
    rows: list[ItemAnnotation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(ItemAnnotation.model_validate(json.loads(line)))
    return rows


def latest_annotations_by_item(bundle_root: Path) -> dict[str, ItemAnnotation]:
    latest: dict[str, ItemAnnotation] = {}
    for ann in load_annotation_history(bundle_root):
        prior = latest.get(ann.item_id)
        if prior is None or ann.created_at >= prior.created_at:
            latest[ann.item_id] = ann
    return latest


def latest_annotation(bundle_root: Path, item_id: str) -> ItemAnnotation | None:
    return latest_annotations_by_item(bundle_root).get(item_id)


def append_annotation(
    bundle_root: Path,
    *,
    item_id: str,
    reviewer_id: str,
    failure_class: FailureClass,
    notes: str = "",
    corpus_spot_check: CorpusSpotCheckStatus = CorpusSpotCheckStatus.PENDING,
    proposed_overrides: ProposedOverrides | None = None,
    repro_context: ReproContextSnapshot | None = None,
    annotation_id: str | None = None,
) -> ItemAnnotation:
    path = annotations_path(bundle_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = ItemAnnotation(
        annotation_id=annotation_id or str(uuid.uuid4()),
        item_id=item_id,
        reviewer_id=reviewer_id,
        failure_class=failure_class,
        notes=notes,
        corpus_spot_check=corpus_spot_check,
        proposed_overrides=proposed_overrides,
        repro_context=repro_context,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return record
