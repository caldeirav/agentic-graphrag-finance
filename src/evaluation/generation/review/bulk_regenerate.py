"""Bulk regeneration for boilerplate and queue-driven item fixes (018)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.generation.review.csv_annotations import _load_item_ids_file, list_boilerplate_comparison_items
from evaluation.generation.review.feedback import BOILERPLATE_REGEN_FEEDBACK
from evaluation.generation.review.regenerate_item import regenerate_item


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"


@dataclass
class BulkRegenerateReport:
    targeted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped_dry_run: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


def _run_bulk_regenerate(
    *,
    bundle_root: Path,
    targets: list[tuple[str, str]],
    feedback: str,
    repo_root: Path | None,
    dry_run: bool,
    progress: Callable[[str], None] | None,
    label: str,
) -> BulkRegenerateReport:
    """Process (item_id, preview) targets with optional progress logging."""
    report = BulkRegenerateReport(targeted=len(targets))
    log = progress or (lambda _msg: None)
    if dry_run:
        report.skipped_dry_run = len(targets)
        return report
    if not targets:
        log(f"{label}: nothing to do")
        return report

    log(f"{label}: starting {len(targets)} item(s) (Gemini regen per item)...")
    started = time.perf_counter()
    for index, (item_id, preview) in enumerate(targets, start=1):
        log(f"{label}: [{index}/{len(targets)}] regenerating {item_id} — {preview}")
        item_started = time.perf_counter()
        try:
            regenerate_item(
                bundle_root,
                item_id=item_id,
                feedback=feedback,
                repo_root=repo_root,
                dry_run=False,
            )
            report.succeeded += 1
            elapsed = time.perf_counter() - item_started
            log(
                f"{label}: [{index}/{len(targets)}] OK {item_id} "
                f"({elapsed:.1f}s, {report.succeeded} succeeded / {report.failed} failed)"
            )
        except Exception as exc:
            report.failed += 1
            report.failures.append({"item_id": item_id, "error": str(exc)})
            elapsed = time.perf_counter() - item_started
            log(
                f"{label}: [{index}/{len(targets)}] FAILED {item_id} "
                f"({elapsed:.1f}s): {exc}"
            )
    total = time.perf_counter() - started
    log(
        f"{label}: complete — targeted={report.targeted} succeeded={report.succeeded} "
        f"failed={report.failed} elapsed={_format_duration(total)}"
    )
    return report


def regenerate_boilerplate_items(
    bundle_root: Path,
    *,
    item_ids_file: Path | None = None,
    feedback: str = BOILERPLATE_REGEN_FEEDBACK,
    repo_root: Path | None = None,
    dry_run: bool = False,
    max_items: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> BulkRegenerateReport:
    """Regenerate comparison items whose canonical answer is boilerplate."""
    item_ids: list[str] | None = None
    if item_ids_file is not None:
        item_ids = _load_item_ids_file(item_ids_file)
    items = list_boilerplate_comparison_items(bundle_root, item_ids=item_ids)
    if max_items is not None:
        items = items[:max_items]

    targets = [
        (
            item.item_id,
            (item.ground_truth.answer or "")[:80].replace("\n", " "),
        )
        for item in items
    ]
    return _run_bulk_regenerate(
        bundle_root=bundle_root,
        targets=targets,
        feedback=feedback,
        repo_root=repo_root,
        dry_run=dry_run,
        progress=progress,
        label="fix-boilerplate",
    )


def regenerate_items_from_file(
    bundle_root: Path,
    item_ids_file: Path,
    *,
    feedback: str = "",
    repo_root: Path | None = None,
    dry_run: bool = False,
    max_items: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> BulkRegenerateReport:
    """Regenerate explicit item_ids (e.g. from annotated CSV export)."""
    item_ids = _load_item_ids_file(item_ids_file)
    if max_items is not None:
        item_ids = item_ids[:max_items]
    targets = [(item_id, "") for item_id in item_ids]
    return _run_bulk_regenerate(
        bundle_root=bundle_root,
        targets=targets,
        feedback=feedback,
        repo_root=repo_root,
        dry_run=dry_run,
        progress=progress,
        label="regenerate-items",
    )


def write_bulk_regenerate_report(bundle_root: Path, report: BulkRegenerateReport) -> Path:
    path = bundle_root / "bulk_regenerate_report.json"
    path.write_text(
        json.dumps(
            {
                "targeted": report.targeted,
                "succeeded": report.succeeded,
                "failed": report.failed,
                "skipped_dry_run": report.skipped_dry_run,
                "failures": report.failures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
