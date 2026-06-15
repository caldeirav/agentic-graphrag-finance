"""Publish audit sampling and sign-off for custom-judge v2.0 (017)."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path

from models.benchmark_generation import GeneratedBenchmarkItem, PublishAuditRecord


def _report_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def stratified_audit_sample(
    items: list[GeneratedBenchmarkItem],
    *,
    sample_size: int = 20,
    seed: int = 0,
) -> list[str]:
    """Pick a stratified sample by inspiration_profile and answer_type."""
    if not items:
        return []
    if len(items) <= sample_size:
        return sorted(item.item_id for item in items)
    buckets: dict[tuple[str, str], list[str]] = {}
    for item in items:
        profile = item.inspiration_profile
        answer_type = (item.answer_type.value if item.answer_type else "unknown")
        buckets.setdefault((profile, answer_type), []).append(item.item_id)
    rng = random.Random(seed)
    selected: list[str] = []
    bucket_keys = sorted(buckets.keys())
    per_bucket = max(1, sample_size // max(len(bucket_keys), 1))
    for key in bucket_keys:
        ids = sorted(buckets[key])
        rng.shuffle(ids)
        selected.extend(ids[:per_bucket])
    remaining = sample_size - len(selected)
    if remaining > 0:
        pool = sorted({item.item_id for item in items if item.item_id not in selected})
        rng.shuffle(pool)
        selected.extend(pool[:remaining])
    return sorted(selected[:sample_size])


def write_audit_sample(
    draft_dir: Path,
    items: list[GeneratedBenchmarkItem],
    *,
    seed: int = 0,
) -> Path:
    """Write pre-signoff stratified audit list."""
    sample_ids = stratified_audit_sample(items, seed=seed)
    payload = {
        "audit_sample_size": len(sample_ids),
        "audit_sample_item_ids": sample_ids,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    path = draft_dir / "publish_audit.sample.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_publish_audit(
    draft_dir: Path,
    *,
    operator_id: str,
    audit_item_ids: list[str],
) -> PublishAuditRecord:
    """Write signed publish audit record."""
    record = PublishAuditRecord(
        audit_sample_size=len(audit_item_ids),
        audit_sample_item_ids=sorted(audit_item_ids),
        operator_id=operator_id,
        signed_off_at=datetime.now(UTC),
        feasibility_report_hash=_report_hash(draft_dir / "feasibility_report.json"),
        scorability_report_hash=_report_hash(draft_dir / "scorability_report.json"),
    )
    path = draft_dir / "publish_audit.json"
    path.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def load_publish_audit(bundle_root: Path) -> PublishAuditRecord | None:
    path = bundle_root / "publish_audit.json"
    if not path.is_file():
        return None
    return PublishAuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
