"""CSV-based annotation import/export for dataset quality review (018)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.comparison_gt import is_boilerplate_comparison_answer, is_comparison_item
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.overrides import apply_overrides, load_regenerated_item_ids
from evaluation.generation.review.queue import build_review_queue
from evaluation.generation.review.review_pack import build_review_pack_rows
from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    FailureClass,
    GeneratedBenchmarkItem,
    ProposedOverrides,
    ReviewQueueEntry,
)
from models.evaluation import GroundTruth

# Columns reviewers fill in; remaining columns are context (exported, ignored on import).
ANNOTATION_INPUT_COLUMNS = frozenset(
    {
        "failure_class",
        "corpus_spot_check",
        "notes",
        "proposed_answer",
        "proposed_question",
        "apply",
    }
)

ANNOTATION_SHEET_COLUMNS = [
    "item_id",
    "priority_tier",
    "priority_score",
    "mrr",
    "ndcg_at_10",
    "outcome_score",
    "inspiration_profile",
    "is_boilerplate_comparison",
    "question",
    "canonical_answer",
    "required_claims",
    "section_paths",
    "failure_class",
    "corpus_spot_check",
    "notes",
    "proposed_answer",
    "proposed_question",
    "apply",
]


@dataclass
class CsvImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    annotation_ids: list[str] = field(default_factory=list)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _parse_failure_class(value: str) -> FailureClass | None:
    text = value.strip()
    if not text:
        return None
    try:
        return FailureClass(text)
    except ValueError:
        return None


def _parse_spot_check(value: str) -> CorpusSpotCheckStatus:
    text = value.strip().lower()
    if text in {"passed", "pass", "yes", "y", "1", "true"}:
        return CorpusSpotCheckStatus.PASSED
    if text in {"failed", "fail", "no", "n", "0", "false"}:
        return CorpusSpotCheckStatus.FAILED
    return CorpusSpotCheckStatus.PENDING


def _load_item_ids_file(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(i) for i in payload]
    if "entries" in payload:
        return [str(e["item_id"]) for e in payload["entries"]]
    return [str(i) for i in payload.get("item_ids", [])]


def list_boilerplate_comparison_items(
    bundle_root: Path,
    *,
    item_ids: list[str] | None = None,
) -> list[GeneratedBenchmarkItem]:
    root = resolve_draft_bundle(bundle_root)
    items = load_dev_split_items(root / "items" / "dev.jsonl")
    allowed = set(item_ids) if item_ids else None
    hits: list[GeneratedBenchmarkItem] = []
    for item in items:
        if allowed is not None and item.item_id not in allowed:
            continue
        if not is_comparison_item(item):
            continue
        answer = (item.ground_truth.answer or "").strip()
        if is_boilerplate_comparison_answer(answer):
            hits.append(item)
    return hits


def build_annotation_sheet_rows(
    bundle_root: Path,
    item_ids: list[str],
    *,
    repro_input: Path | None = None,
    variant: str = "graph-full",
    queue_by_id: dict[str, ReviewQueueEntry] | None = None,
) -> list[dict[str, str]]:
    pack_rows = {r["item_id"]: r for r in build_review_pack_rows(
        bundle_root,
        item_ids,
        repro_input=repro_input,
        variant=variant,
    )}
    root = resolve_draft_bundle(bundle_root)
    items = {i.item_id: i for i in load_dev_split_items(root / "items" / "dev.jsonl")}
    if queue_by_id is None and repro_input is not None:
        queue_by_id = {e.item_id: e for e in build_review_queue(
            bundle_root,
            repro_input=repro_input,
            variant=variant,
        )}

    rows: list[dict[str, str]] = []
    for item_id in item_ids:
        item = items.get(item_id)
        pack = pack_rows.get(item_id, {})
        queue = (queue_by_id or {}).get(item_id)
        boilerplate = ""
        if item is not None:
            answer = (item.ground_truth.answer or "").strip()
            boilerplate = "yes" if is_boilerplate_comparison_answer(answer) else "no"
        rows.append(
            {
                "item_id": item_id,
                "priority_tier": str(queue.priority_tier) if queue else "",
                "priority_score": f"{queue.priority_score:.3f}" if queue else "",
                "mrr": pack.get("mrr", ""),
                "ndcg_at_10": pack.get("ndcg_at_10", ""),
                "outcome_score": pack.get("outcome_score", ""),
                "inspiration_profile": pack.get("inspiration_profile", ""),
                "is_boilerplate_comparison": boilerplate,
                "question": pack.get("question", ""),
                "canonical_answer": pack.get("canonical_answer", ""),
                "required_claims": pack.get("required_claims", ""),
                "section_paths": pack.get("section_paths", ""),
                "failure_class": "",
                "corpus_spot_check": "",
                "notes": "",
                "proposed_answer": "",
                "proposed_question": "",
                "apply": "",
            }
        )
    return rows


def write_annotation_sheet(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_SHEET_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in ANNOTATION_SHEET_COLUMNS})
    return path


def import_annotations_from_csv(
    bundle_root: Path,
    csv_path: Path,
    *,
    reviewer_id: str,
    apply_after: bool = False,
    dry_run: bool = False,
    skip_failed: bool = False,
    force_agent_failure: bool = False,
) -> CsvImportResult:
    resolve_draft_bundle(bundle_root)
    result = CsvImportResult()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "item_id" not in reader.fieldnames:
            msg = "CSV must include item_id column"
            raise ValueError(msg)
        for line_no, row in enumerate(reader, start=2):
            item_id = (row.get("item_id") or "").strip()
            if not item_id:
                result.skipped += 1
                continue

            failure_class = _parse_failure_class(row.get("failure_class") or "")
            if failure_class is None:
                result.skipped += 1
                continue

            spot_check = _parse_spot_check(row.get("corpus_spot_check") or "")
            if spot_check != CorpusSpotCheckStatus.PASSED:
                result.skipped += 1
                continue

            apply_flag = row.get("apply", "")
            if apply_flag.strip() and not _parse_bool(apply_flag):
                result.skipped += 1
                continue

            proposed_answer = (row.get("proposed_answer") or "").strip()
            proposed_question = (row.get("proposed_question") or "").strip()
            if not proposed_answer and not proposed_question:
                result.skipped += 1
                result.errors.append(f"line {line_no} {item_id}: no proposed_answer or proposed_question")
                continue

            overrides = ProposedOverrides(
                question=proposed_question or None,
                ground_truth=GroundTruth(answer=proposed_answer) if proposed_answer else None,
            )
            notes = (row.get("notes") or "").strip()

            if dry_run:
                result.imported += 1
                continue

            record = append_annotation(
                bundle_root,
                item_id=item_id,
                reviewer_id=reviewer_id,
                failure_class=failure_class,
                notes=notes,
                corpus_spot_check=spot_check,
                proposed_overrides=overrides,
            )
            result.imported += 1
            result.annotation_ids.append(record.annotation_id)

    if apply_after and not dry_run and result.annotation_ids:
        changelog = apply_overrides(
            bundle_root,
            annotation_ids=set(result.annotation_ids),
            skip_failed=skip_failed,
            force_agent_failure=force_agent_failure,
        )
        rejected = sum(1 for entry in changelog if entry.validation_outcome == "rejected")
        if rejected and not skip_failed:
            result.errors.append(f"apply-overrides rejected {rejected} item(s)")

    return result
