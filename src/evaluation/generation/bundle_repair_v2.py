"""Repair published custom-judge v2 bundles (section paths, numeric GT, relevance)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.generation.item_validator import load_graph_paths, validate_item
from evaluation.generation.numeric_gt import is_numeric_gt_string, normalize_numeric_gt
from evaluation.generation.path_sanitize import (
    filter_canonical_graph_paths,
    infer_section_hints,
    is_corrupt_section_path,
    needs_v2_path_repair,
    pick_section_path_for_accession,
)
from evaluation.generation.section_paths import resolve_section_paths
from evaluation.generation.v2_item_normalize import normalize_v2_item
from evaluation.reproduction.relevance import materialize_relevance_labels
from evaluation.reproduction.stratum import assign_primary_evidence_source
from models.benchmark_generation import GeneratedBenchmarkItem


@dataclass
class RepairReport:
    items_scanned: int = 0
    paths_repaired: int = 0
    numeric_normalized: int = 0
    index_paths_removed: int = 0
    v2_cohort_repaired: int = 0
    injection_suppressed: int = 0
    item_ids_changed: list[str] = field(default_factory=list)


def _row_to_item(row: dict) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(row)


def repair_expected_section_paths_row(
    row: dict,
    graph_paths: set[str],
    snapshot_accessions: set[str],
    *,
    repair_version: str = "v2",
) -> tuple[list[str], bool]:
    """Return canonical paths and whether they changed."""
    bindings = row.get("expected_bindings") or {}
    accessions = list(bindings.get("accessions") or [])
    gt = row.get("ground_truth") or {}
    answer = str(gt.get("answer") or "")
    claims = " ".join(gt.get("required_claims") or [])
    hints = infer_section_hints(
        row.get("question") or "",
        answer=answer,
        gt_text=claims,
    )

    raw_paths = list(row.get("expected_section_paths") or [])
    canonical, unresolved = resolve_section_paths(
        raw_paths,
        graph_paths,
        snapshot_accessions=snapshot_accessions,
    )
    corrupt = [p for p in raw_paths if is_corrupt_section_path(p)]
    needs_repair = corrupt or unresolved or not canonical
    if repair_version == "v2":
        needs_repair = needs_repair or needs_v2_path_repair(row)

    if not needs_repair and canonical == raw_paths:
        return canonical, False

    repaired: list[str] = []
    if accessions:
        for acc in accessions:
            picked = pick_section_path_for_accession(
                acc,
                graph_paths,
                hints,
                question=row.get("question") or "",
                answer=answer,
                gt_text=claims,
            )
            if picked:
                repaired.append(picked)
    if not repaired:
        repaired = canonical

    resolved, _still_bad = resolve_section_paths(
        repaired,
        graph_paths,
        snapshot_accessions=snapshot_accessions,
    )
    if resolved:
        changed = resolved != raw_paths
        return resolved, changed
    return canonical if canonical else raw_paths, bool(corrupt or unresolved)


def repair_row(
    row: dict,
    graph_paths: set[str],
    snapshot_accessions: set[str],
    bundle_version: str,
    *,
    repair_version: str = "v2",
) -> tuple[dict, bool, bool]:
    """Return (row, changed, v2_cohort)."""
    changed = False
    v2_needed = repair_version == "v2" and needs_v2_path_repair(row)
    paths, path_changed = repair_expected_section_paths_row(
        row,
        graph_paths,
        snapshot_accessions,
        repair_version=repair_version,
    )
    if path_changed:
        row = dict(row)
        row["expected_section_paths"] = paths
        row["path_repair_version"] = repair_version
        row["suppress_benchmark_path_injection"] = True
        changed = True
    elif row.get("suppress_benchmark_path_injection"):
        row = dict(row)

    gt = dict(row.get("ground_truth") or {})
    answer = str(gt.get("answer") or "").strip()
    if answer and is_numeric_gt_string(answer):
        normalized = normalize_numeric_gt(answer)
        if normalized != answer:
            gt["answer"] = normalized
            row = dict(row)
            row["ground_truth"] = gt
            changed = True

    if changed:
        item = normalize_v2_item(_row_to_item(row))
        validated = validate_item(
            item,
            graph_paths=graph_paths,
            snapshot_accessions=snapshot_accessions,
            bundle_version=bundle_version,
        )
        row = validated.model_dump(mode="json")
    return row, changed, v2_needed and path_changed


def repair_bundle(
    bundle_root: Path,
    *,
    split: str = "dev",
    dry_run: bool = False,
    rematerialize_relevance: bool = True,
    repair_version: str = "v2",
) -> RepairReport:
    bundle_root = bundle_root.resolve()
    report = RepairReport()
    index_path = bundle_root / "corpus" / "graph_node_index.json"
    raw_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    graph_paths = filter_canonical_graph_paths(raw_paths)
    report.index_paths_removed = len(raw_paths) - len(graph_paths)

    manifest_path = bundle_root / "manifest.json"
    bundle_version = "2.0.0"
    if manifest_path.is_file():
        bundle_version = str(
            json.loads(manifest_path.read_text(encoding="utf-8")).get("version") or bundle_version
        )

    snapshot_accessions: set[str] = set()
    items_path = bundle_root / "items" / f"{split}.jsonl"
    rows = [
        json.loads(line)
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        for acc in (row.get("expected_bindings") or {}).get("accessions") or []:
            snapshot_accessions.add(acc)

    new_rows: list[dict] = []
    for row in rows:
        report.items_scanned += 1
        updated, changed, v2_cohort = repair_row(
            row,
            graph_paths,
            snapshot_accessions,
            bundle_version,
            repair_version=repair_version,
        )
        if changed:
            report.paths_repaired += 1
            report.item_ids_changed.append(updated["item_id"])
            raw_answer = (row.get("ground_truth") or {}).get("answer")
            new_answer = (updated.get("ground_truth") or {}).get("answer")
            if raw_answer != new_answer:
                report.numeric_normalized += 1
        if v2_cohort:
            report.v2_cohort_repaired += 1
        if updated.get("suppress_benchmark_path_injection"):
            report.injection_suppressed += 1
        new_rows.append(updated)

    if dry_run:
        return report

    items_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in new_rows) + "\n",
        encoding="utf-8",
    )

    if report.index_paths_removed and index_path.is_file():
        index_path.write_text(
            json.dumps({"paths": sorted(graph_paths)}, indent=2) + "\n",
            encoding="utf-8",
        )

    if rematerialize_relevance:
        materialize_relevance_labels(bundle_root, split=split)
        subset_ids = set(report.item_ids_changed)
        for row in new_rows:
            if assign_primary_evidence_source(row.get("relevant_chunk_ids") or []) == "xbrl":
                subset_ids.add(row["item_id"])
        if subset_ids:
            subset_rows = [r for r in new_rows if r["item_id"] in subset_ids]
            subset_path = bundle_root / "items" / f"{split}_repair_subset.jsonl"
            subset_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in subset_rows) + "\n",
                encoding="utf-8",
            )
            (bundle_root / "repair_subset_item_ids.json").write_text(
                json.dumps(sorted(subset_ids), indent=2) + "\n",
                encoding="utf-8",
            )

    return report
