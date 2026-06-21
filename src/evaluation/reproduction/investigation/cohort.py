"""Tier-1 cohort freeze from review queue (019)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.reproduction.investigation._loaders import load_review_queue_entries
from models.investigation import Tier1CohortEntry, Tier1CohortFile


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_tier1_cohort(queue_path: Path, output_path: Path) -> Tier1CohortFile:
    entries = load_review_queue_entries(queue_path)
    tier1 = [e for e in entries if e.priority_tier == 1]
    if not tier1:
        tier1 = entries
    cohort = Tier1CohortFile(
        source_queue_path=str(queue_path),
        source_queue_hash=_sha256_path(queue_path),
        exported_at=datetime.now(UTC),
        item_ids=[e.item_id for e in tier1],
        entries=[
            Tier1CohortEntry(
                item_id=e.item_id,
                priority_tier=e.priority_tier,
                priority_score=e.priority_score,
            )
            for e in tier1
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cohort.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return cohort


def load_tier1_cohort(path: Path) -> Tier1CohortFile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Tier1CohortFile.model_validate(payload)
