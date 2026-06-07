"""Draft and published bundle assembly for custom-judge datasets (011).

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

from evaluation.generation.gt_classifier import is_numeric_answer_gt
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


def _comparison_tag(tag: str) -> bool:
    lowered = (tag or "").lower()
    return any(kw in lowered for kw in ("comparison", "multi-hop", "cross-filing", "agentic-multi"))


def _reference_tag(tag: str) -> bool:
    return "reference" in (tag or "").lower()


def _corpus_accessions(bundle_root: Path) -> set[str]:
    index_path = bundle_root / manifest_corpus_index_path(bundle_root)
    if not index_path.is_file():
        return set()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    accessions: set[str] = set()
    for path in data.get("paths", []):
        acc = str(path).split("/")[0]
        if acc:
            accessions.add(acc)
    for key in ("accessions", "nodes"):
        for entry in data.get(key, []):
            if isinstance(entry, str):
                accessions.add(entry.split("/")[0])
    return accessions


def manifest_corpus_index_path(bundle_root: Path) -> Path:
    manifest_path = bundle_root / "manifest.json"
    if manifest_path.is_file():
        manifest = DatasetManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
        rel = manifest.corpus_bundle.graph_node_index_path
        return bundle_root / rel
    return bundle_root / "corpus" / "graph_node_index.json"


def validate_bundle_feasibility(
    bundle_root: Path,
    items_path: Path,
) -> dict[str, object]:
    """Return feasibility report; blocked items fail publish gates."""
    items = [
        GeneratedBenchmarkItem.model_validate(json.loads(line))
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    corpus_accessions = _corpus_accessions(bundle_root)
    blocked: list[dict[str, str]] = []
    for item in items:
        tag = item.question_type_tag
        accs = list(dict.fromkeys(item.expected_bindings.accessions))
        if _comparison_tag(tag) and len(accs) < 2:
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "comparison_bindings",
                    "detail": f"expected {len(accs)} accessions, need >= 2",
                }
            )
        if _reference_tag(tag) and accs:
            missing = [a for a in accs if a not in corpus_accessions]
            if missing and corpus_accessions:
                blocked.append(
                    {
                        "item_id": item.item_id,
                        "reason": "reference_corpus",
                        "detail": f"missing accessions: {', '.join(missing)}",
                    }
                )
        gt = item.ground_truth
        if gt.answer and not is_numeric_answer_gt(gt.answer):
            claims = gt.required_claims or []
            if not claims:
                blocked.append(
                    {
                        "item_id": item.item_id,
                        "reason": "required_claims",
                        "detail": "narrative answer-GT missing required_claims",
                    }
                )
        if is_rubric_only_routing(item) and not (gt.rubric or "").strip():
            blocked.append(
                {
                    "item_id": item.item_id,
                    "reason": "rubric_route",
                    "detail": "rubric-only item missing rubric text",
                }
            )
    return {
        "blocked_count": len(blocked),
        "blocked_items": blocked,
        "item_count": len(items),
    }


def is_rubric_only_routing(item: GeneratedBenchmarkItem) -> bool:
    return _comparison_tag(item.question_type_tag) or _reference_tag(item.question_type_tag)


def check_publish_gates(
    manifest: DatasetManifest,
    report: GenerationReport,
    *,
    min_items: int = 200,
    min_pass_rate: float = 0.95,
    skip_gates: bool = False,
    bundle_root: Path | None = None,
) -> None:
    if skip_gates:
        return
    if manifest.item_count < min_items:
        msg = f"Publish gate failed: item_count {manifest.item_count} < {min_items}"
        raise ValueError(msg)
    if report.pass_rate < min_pass_rate:
        msg = f"Publish gate failed: pass_rate {report.pass_rate} < {min_pass_rate}"
        raise ValueError(msg)
    if bundle_root is not None:
        items_path = bundle_root / "items" / "dev.jsonl"
        if items_path.is_file():
            feasibility = validate_bundle_feasibility(bundle_root, items_path)
            if int(feasibility["blocked_count"]) > 0:
                first = feasibility["blocked_items"][0]  # type: ignore[index]
                msg = (
                    f"Publish gate failed: {feasibility['blocked_count']} infeasible item(s); "
                    f"first={first['item_id']} ({first['reason']})"
                )
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
    check_publish_gates(
        manifest, report, min_items=min_items, skip_gates=skip_gates, bundle_root=draft_dir
    )
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
