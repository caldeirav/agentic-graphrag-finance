"""Migrate custom-judge bundle v1.0.0 → v1.1.0 draft (016)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.generation.bundle import (
    _comparison_tag,
    _corpus_accessions,
    _reference_tag,
    items_hash,
    profile_counts,
    validate_bundle_feasibility,
)
from evaluation.generation.gt_classifier import is_numeric_answer_gt
from models.benchmark_generation import DatasetManifest, GeneratedBenchmarkItem, GenerationReport

RUBRIC_ONLY_TAG_KEYWORDS = (
    "comparison",
    "multi-hop",
    "reference-following",
    "agentic-multi-hop",
    "cross-filing",
)


@dataclass
class ChangelogEntry:
    item_id: str
    change_types: list[str] = field(default_factory=list)
    summary: str = ""
    requires_agent_rerun: bool = False


def is_rubric_only_tag(tag: str) -> bool:
    lowered = (tag or "").lower()
    return any(kw in lowered for kw in RUBRIC_ONLY_TAG_KEYWORDS)


def derive_required_claims(answer: str, *, min_claims: int = 2) -> list[str]:
    text = (answer or "").strip()
    if not text:
        return []
    sentences = [s.strip() for s in re.split(r"[.;]\s+", text) if len(s.strip()) > 15]
    claims = sentences[:8] if len(sentences) >= min_claims else []
    if len(claims) < min_claims:
        chunks = [
            text[i : i + 120].strip()
            for i in range(0, len(text), 120)
            if text[i : i + 120].strip()
        ]
        claims = chunks[:8]
    if len(claims) < min_claims and text:
        words = text.split()
        if len(words) >= 4:
            mid = max(1, len(words) // 2)
            claims = [" ".join(words[:mid]).strip(), " ".join(words[mid:]).strip()]
        else:
            claims = [text, text]
    return [c for c in claims if c][:8]


def repair_bindings(
    item: GeneratedBenchmarkItem,
    corpus_accessions: set[str],
) -> tuple[GeneratedBenchmarkItem, ChangelogEntry | None]:
    """Repair infeasible comparison/reference bindings using corpus accessions."""
    bindings = item.expected_bindings
    accs = list(dict.fromkeys(bindings.accessions))
    changed = False
    summary_parts: list[str] = []

    if _comparison_tag(item.question_type_tag) and len(accs) < 2:
        candidates = sorted(a for a in corpus_accessions if a not in accs)
        if candidates:
            accs.append(candidates[0])
            changed = True
            summary_parts.append(f"added comparison partner {candidates[0]}")

    if _reference_tag(item.question_type_tag) and accs:
        missing = [a for a in accs if a not in corpus_accessions]
        if missing and corpus_accessions:
            valid = [a for a in accs if a in corpus_accessions]
            if valid and valid != accs:
                accs = valid
                changed = True
                summary_parts.append(f"dropped unreachable accessions: {', '.join(missing)}")

    if not changed:
        return item, None

    updated_bindings = bindings.model_copy(update={"accessions": accs})
    entry = ChangelogEntry(
        item_id=item.item_id,
        change_types=["bindings"],
        summary="; ".join(summary_parts),
        requires_agent_rerun=True,
    )
    return item.model_copy(update={"expected_bindings": updated_bindings}), entry


def migrate_item(item: GeneratedBenchmarkItem) -> tuple[GeneratedBenchmarkItem, ChangelogEntry | None]:
    changes: list[str] = []
    summary_parts: list[str] = []
    requires_rerun = False
    gt = item.ground_truth.model_copy(deep=True)

    if is_rubric_only_tag(item.question_type_tag) and gt.answer:
        rubric_text = gt.rubric or gt.answer
        gt = gt.model_copy(update={"answer": None, "rubric": rubric_text, "required_claims": None})
        changes.append("rubric_route")
        summary_parts.append("routed to rubric-only grading")
        requires_rerun = True

    if gt.answer and not is_numeric_answer_gt(gt.answer):
        claims = derive_required_claims(gt.answer)
        if claims and gt.required_claims != claims:
            gt = gt.model_copy(update={"required_claims": claims})
            changes.append("ground_truth")
            summary_parts.append("attached required_claims")

    bindings = item.expected_bindings
    if bindings and is_rubric_only_tag(item.question_type_tag):
        accs = list(dict.fromkeys(bindings.accessions))
        if len(accs) < 2 and item.multi_filing_required:
            summary_parts.append("comparison item retains single accession (review bindings)")
            changes.append("bindings")

    if not changes:
        return item, None

    updated = item.model_copy(update={"ground_truth": gt})
    entry = ChangelogEntry(
        item_id=item.item_id,
        change_types=changes,
        summary="; ".join(summary_parts) or "updated",
        requires_agent_rerun=requires_rerun,
    )
    return updated, entry


def load_items(path: Path) -> list[GeneratedBenchmarkItem]:
    items: list[GeneratedBenchmarkItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        items.append(GeneratedBenchmarkItem.model_validate(json.loads(line)))
    return items


def write_items(path: Path, items: list[GeneratedBenchmarkItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(i.model_dump(mode="json"), sort_keys=True) for i in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_changelog(path: Path, entries: list[ChangelogEntry]) -> None:
    lines = ["# CHANGELOG v1.1.0 vs v1.0.0", ""]
    for entry in entries:
        types = ", ".join(entry.change_types)
        rerun = "true" if entry.requires_agent_rerun else "false"
        lines.append(f"### {entry.item_id}")
        lines.append(f"- **change_types**: {types}")
        lines.append(f"- **summary**: {entry.summary}")
        lines.append(f"- **requires_agent_rerun**: {rerun}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_draft_from_parent(
    parent_root: Path,
    draft_dir: Path,
    *,
    parent_version: str = "1.0.0",
    split: str = "dev",
) -> tuple[list[GeneratedBenchmarkItem], list[ChangelogEntry]]:
    """Copy parent bundle and apply v1.1.0 item migrations."""
    if draft_dir.exists():
        shutil.rmtree(draft_dir)
    shutil.copytree(parent_root, draft_dir)

    report_src = parent_root / "generation_report.json"
    if report_src.is_file():
        shutil.copy2(report_src, draft_dir / "generation_report.json")
    else:
        item_count = len([ln for ln in (draft_dir / "items" / f"{split}.jsonl").read_text().splitlines() if ln.strip()])
        report = GenerationReport(
            run_id=f"migrate-v1.1.0-{parent_version}",
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
    corpus_accessions = _corpus_accessions(draft_dir)
    migrated: list[GeneratedBenchmarkItem] = []
    changelog: list[ChangelogEntry] = []
    for item in load_items(items_path):
        updated, entry = migrate_item(item)
        updated, bind_entry = repair_bindings(updated, corpus_accessions)
        migrated.append(updated)
        for e in (entry, bind_entry):
            if e is not None:
                changelog.append(e)
    write_items(items_path, migrated)
    write_changelog(draft_dir / "CHANGELOG.md", changelog)

    parent_manifest = DatasetManifest.model_validate(
        json.loads((parent_root / "manifest.json").read_text(encoding="utf-8"))
    )
    manifest = parent_manifest.model_copy(
        update={
            "version": "1.1.0-draft",
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
    feasibility = validate_bundle_feasibility(draft_dir, items_path)
    (draft_dir / "feasibility_report.json").write_text(
        json.dumps(feasibility, indent=2) + "\n",
        encoding="utf-8",
    )
    return migrated, changelog
