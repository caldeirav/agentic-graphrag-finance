"""Draft and published bundle assembly for custom-judge datasets (012).

Extend workflow: parent published artifacts are immutable. ``extend`` copies parent
items/corpus into a new draft; delta issuers may add a new composite ``snapshot_id``
while reusing unchanged parent issuer snapshots when filings overlap.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from models.benchmark_generation import (
    CorpusBundle,
    DatasetManifest,
    DatasetStatus,
    GeneratedBenchmarkItem,
    GenerationConfig,
    GenerationReport,
    SamplingManifest,
)


def items_hash(items_path: Path) -> str:
    lines = [
        line.strip()
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [json.loads(line) for line in lines]
    rows.sort(key=lambda r: r["item_id"])
    body = "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def profile_counts(items: list[GeneratedBenchmarkItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.inspiration_profile] = counts.get(item.inspiration_profile, 0) + 1
    return counts


def write_draft_manifest(
    *,
    draft_dir: Path,
    config: GenerationConfig,
    sampling: SamplingManifest,
    bundle: CorpusBundle,
    report: GenerationReport,
    items_path: Path,
    version: str = "0.0.0-draft",
) -> DatasetManifest:
    manifest = DatasetManifest(
        version=version,
        status=DatasetStatus.DRAFT,
        item_count=len([ln for ln in items_path.read_text().splitlines() if ln.strip()]),
        items_hash=items_hash(items_path),
        sampling_manifest_path="sampling_manifest.json",
        generation_config_path="generation_config.yaml",
        generation_report_path="generation_report.json",
        corpus_bundle=bundle,
        generation_judge_version=config.generation_judge_version,
        evaluation_judge_version=config.evaluation_judge_version,
        profile_counts=profile_counts(
            [
                GeneratedBenchmarkItem.model_validate(json.loads(line))
                for line in items_path.read_text().splitlines()
                if line.strip()
            ]
        ),
    )
    (draft_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (draft_dir / "generation_config.yaml").write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    )
    (draft_dir / "generation_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n"
    )
    return manifest


def check_publish_gates(
    manifest: DatasetManifest,
    report: GenerationReport,
    *,
    min_items: int = 200,
    min_pass_rate: float = 0.95,
    skip_gates: bool = False,
) -> None:
    if skip_gates:
        return
    if manifest.item_count < min_items:
        msg = f"Publish gate failed: item_count {manifest.item_count} < {min_items}"
        raise ValueError(msg)
    if report.pass_rate < min_pass_rate:
        msg = f"Publish gate failed: pass_rate {report.pass_rate} < {min_pass_rate}"
        raise ValueError(msg)


def publish_draft(
    draft_dir: Path,
    *,
    version: str,
    published_root: Path,
    published_by: str = "operator",
    min_items: int = 200,
    skip_gates: bool = False,
) -> Path:
    manifest = DatasetManifest.model_validate(
        json.loads((draft_dir / "manifest.json").read_text(encoding="utf-8"))
    )
    report = GenerationReport.model_validate(
        json.loads((draft_dir / "generation_report.json").read_text(encoding="utf-8"))
    )
    check_publish_gates(manifest, report, min_items=min_items, skip_gates=skip_gates)
    dest = published_root / f"v{version}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(draft_dir, dest)
    published = manifest.model_copy(
        update={
            "version": version,
            "status": DatasetStatus.PUBLISHED,
            "published_at": datetime.now(UTC),
            "published_by": published_by,
        }
    )
    (dest / "manifest.json").write_text(
        json.dumps(published.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    return dest
