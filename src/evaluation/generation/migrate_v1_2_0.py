"""Migrate custom-judge bundle v1.1.0 → v1.2.0 draft (016 outcome calibration)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from evaluation.generation.bundle import (
    items_hash,
    profile_counts,
    question_binding_year_mismatch,
    validate_bundle_feasibility,
    validate_section_reachability,
)
from evaluation.generation.gt_classifier import _NUMERIC_PATTERN, is_numeric_answer_gt
from evaluation.generation.item_validator import load_graph_paths
from evaluation.generation.migrate_v1_1_0 import (
    ChangelogEntry,
    derive_required_claims,
    load_items,
    write_items,
)
from evaluation.generation.section_paths import resolve_section_paths
from evaluation.reproduction.relevance import materialize_relevance_labels
from models.benchmark_generation import DatasetManifest, GeneratedBenchmarkItem, GenerationReport


def _years_in_text(text: str) -> set[int]:
    return {int(y) for y in re.findall(r"20\d{2}", text or "")}


def align_question_to_binding_years(
    question: str,
    fiscal_periods: list[str],
) -> tuple[str, bool]:
    """Replace question years disjoint from fiscal_periods with the latest bound year."""
    period_years = sorted(_years_in_text(" ".join(str(p) for p in fiscal_periods)))
    if not period_years:
        return question, False
    canonical = period_years[-1]
    changed = False

    def _repl(match: re.Match[str]) -> str:
        nonlocal changed
        year = int(match.group(0))
        if year not in period_years:
            changed = True
            return str(canonical)
        return match.group(0)

    aligned = re.sub(r"20\d{2}", _repl, question)
    return aligned, changed


def derive_short_label_claims(answer: str, question: str) -> list[str]:
    """Attach scorable claims for short-label answer-GT (e.g. segment names)."""
    text = (answer or "").strip()
    if not text:
        return []
    if len(text) <= 80:
        claims = [f"The answer is: {text}"]
        q = (question or "").lower()
        if "segment" in q or "business unit" in q or "sector" in q:
            claims.append(f"The response identifies the segment or business unit: {text}")
        if "risk" in q and "category" in q:
            claims.append(f"The response names the risk category: {text}")
        return claims[:4]
    return derive_required_claims(text)


def enhance_required_claims(item: GeneratedBenchmarkItem) -> tuple[GeneratedBenchmarkItem, ChangelogEntry | None]:
    gt = item.ground_truth
    if not gt.answer:
        return item, None
    text = gt.answer.strip()
    if _NUMERIC_PATTERN.match(text):
        return item, None
    claims = list(gt.required_claims or [])
    if len(claims) < 2:
        if is_numeric_answer_gt(text):
            claims = derive_short_label_claims(text, item.question)
        else:
            claims = derive_required_claims(text)
    if not claims:
        claims = derive_required_claims(text)
    if claims == (gt.required_claims or []):
        return item, None
    updated_gt = gt.model_copy(update={"required_claims": claims[:8]})
    entry = ChangelogEntry(
        item_id=item.item_id,
        change_types=["ground_truth"],
        summary="enhanced required_claims for graded value_alignment",
        requires_agent_rerun=False,
    )
    return item.model_copy(update={"ground_truth": updated_gt}), entry


def fix_question_year(item: GeneratedBenchmarkItem) -> tuple[GeneratedBenchmarkItem, ChangelogEntry | None]:
    mismatched, detail = question_binding_year_mismatch(item)
    if not mismatched:
        return item, None
    aligned, _ = align_question_to_binding_years(
        item.question,
        list(item.expected_bindings.fiscal_periods or []),
    )
    if aligned == item.question:
        return item, None
    entry = ChangelogEntry(
        item_id=item.item_id,
        change_types=["question"],
        summary=f"aligned question years to binding ({detail})",
        requires_agent_rerun=True,
    )
    return item.model_copy(update={"question": aligned}), entry


def repair_section_paths(
    item: GeneratedBenchmarkItem,
    graph_paths: set[str],
    corpus_accessions: set[str],
) -> tuple[GeneratedBenchmarkItem, ChangelogEntry | None]:
    paths = list(item.expected_section_paths or [])
    if not paths or not graph_paths:
        return item, None
    resolved, unresolved = resolve_section_paths(
        paths,
        graph_paths,
        snapshot_accessions=corpus_accessions,
    )
    if resolved and not unresolved:
        return item, None
    accs = list(item.expected_bindings.accessions or [])
    acc = accs[0] if accs else ""
    if not acc:
        return item, None
    q = item.question.lower()
    hints: list[str] = []
    if any(k in q for k in ("risk", "item 1a", "1a")):
        hints.extend(["risk", "item 1a", "item1a"])
    if any(k in q for k in ("segment", "business unit", "sector", "grooming", "braun")):
        hints.extend(["business", "segment", "product"])
    if any(k in q for k in ("officer", "role", "counsel", "president", "ceo")):
        hints.extend(["executive", "officer", "director"])
    if "md&a" in q or "mda" in q or "discussion" in q:
        hints.extend(["mda", "management", "discussion"])
    candidate_paths = sorted(
        p
        for p in graph_paths
        if acc.replace("-", "") in p.replace("-", "")
        and any(h in p.lower() for h in hints)
    )
    if not candidate_paths:
        return item, None
    new_path = candidate_paths[0]
    if paths == [new_path]:
        return item, None
    entry = ChangelogEntry(
        item_id=item.item_id,
        change_types=["bindings"],
        summary=f"repaired expected_section_paths → {new_path}",
        requires_agent_rerun=True,
    )
    return item.model_copy(update={"expected_section_paths": [new_path]}), entry


def migrate_item(
    item: GeneratedBenchmarkItem,
    *,
    graph_paths: set[str],
    corpus_accessions: set[str],
) -> tuple[GeneratedBenchmarkItem, list[ChangelogEntry]]:
    entries: list[ChangelogEntry] = []
    updated = item
    for step in (
        lambda i: fix_question_year(i),
        lambda i: repair_section_paths(i, graph_paths, corpus_accessions),
        lambda i: enhance_required_claims(i),
    ):
        updated, entry = step(updated)
        if entry is not None:
            entries.append(entry)
    return updated, entries


def build_draft_from_parent(
    parent_root: Path,
    draft_dir: Path,
    *,
    parent_version: str = "1.1.0",
    split: str = "dev",
) -> tuple[list[GeneratedBenchmarkItem], list[ChangelogEntry]]:
    """Copy parent bundle and apply v1.2.0 item migrations."""
    if draft_dir.exists():
        shutil.rmtree(draft_dir)
    shutil.copytree(parent_root, draft_dir)

    report_src = parent_root / "generation_report.json"
    if report_src.is_file():
        shutil.copy2(report_src, draft_dir / "generation_report.json")
    else:
        items_file = draft_dir / "items" / f"{split}.jsonl"
        item_count = len([ln for ln in items_file.read_text().splitlines() if ln.strip()])
        report = GenerationReport(
            run_id=f"migrate-v1.2.0-{parent_version}",
            candidates_total=item_count,
            accepted_count=item_count,
            rejected_count=0,
            pass_rate=1.0,
            judge_api_calls=0,
            storage_bytes_used=0,
            duration_seconds=0.0,
        )
        (draft_dir / "generation_report.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

    items_path = draft_dir / "items" / f"{split}.jsonl"
    from evaluation.generation.bundle import _corpus_accessions, manifest_corpus_index_path

    index_path = manifest_corpus_index_path(draft_dir)
    graph_paths = load_graph_paths(index_path) if index_path.is_file() else set()
    corpus_accessions = _corpus_accessions(draft_dir)

    migrated: list[GeneratedBenchmarkItem] = []
    changelog: list[ChangelogEntry] = []
    for item in load_items(items_path):
        updated, entries = migrate_item(
            item,
            graph_paths=graph_paths,
            corpus_accessions=corpus_accessions,
        )
        migrated.append(updated)
        changelog.extend(entries)

    write_items(items_path, migrated)
    write_changelog(draft_dir / "CHANGELOG.md", changelog, version="1.2.0", parent=parent_version)

    materialize_relevance_labels(draft_dir, split=split, min_coverage=0.9)

    parent_manifest = DatasetManifest.model_validate(
        json.loads((parent_root / "manifest.json").read_text(encoding="utf-8"))
    )
    manifest = parent_manifest.model_copy(
        update={
            "version": "1.2.0-draft",
            "parent_version": parent_version,
            "item_count": len(migrated),
            "items_hash": items_hash(items_path),
            "profile_counts": profile_counts(migrated),
        }
    )
    (draft_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    reachability = validate_section_reachability(draft_dir, items_path)
    (draft_dir / "reachability_report.json").write_text(
        json.dumps(reachability, indent=2) + "\n",
        encoding="utf-8",
    )
    feasibility = validate_bundle_feasibility(draft_dir, items_path)
    (draft_dir / "feasibility_report.json").write_text(
        json.dumps(feasibility, indent=2) + "\n",
        encoding="utf-8",
    )
    return migrated, changelog


def write_changelog(
    path: Path,
    entries: list[ChangelogEntry],
    *,
    version: str = "1.2.0",
    parent: str = "1.1.0",
) -> None:
    lines = [f"# CHANGELOG v{version} vs v{parent}", ""]
    if not entries:
        lines.append("_No item-level migrations required._")
        lines.append("")
    for entry in entries:
        types = ", ".join(entry.change_types)
        rerun = "true" if entry.requires_agent_rerun else "false"
        lines.append(f"### {entry.item_id}")
        lines.append(f"- **change_types**: {types}")
        lines.append(f"- **summary**: {entry.summary}")
        lines.append(f"- **requires_agent_rerun**: {rerun}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
