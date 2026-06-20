"""Diversity metrics and duplicate-feedback reporting (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from models.benchmark_generation import (
    DiversityReport,
    DuplicateRejectionFeedback,
    ProfileDiversityStats,
)


def duplicate_feedback_path(bundle_root: Path) -> Path:
    return bundle_root / "duplicate_feedback.jsonl"


def load_duplicate_feedback(bundle_root: Path) -> list[DuplicateRejectionFeedback]:
    path = duplicate_feedback_path(bundle_root)
    if not path.is_file():
        return []
    return [
        DuplicateRejectionFeedback.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_duplicate_feedback(bundle_root: Path, record: DuplicateRejectionFeedback) -> None:
    path = duplicate_feedback_path(bundle_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def build_diversity_report(bundle_root: Path, *, baseline_reference: str = "v2.0.0") -> DiversityReport:
    gen_report_path = bundle_root / "generation_report.json"
    candidates_total = 0
    duplicate_count = 0
    if gen_report_path.is_file():
        data = json.loads(gen_report_path.read_text(encoding="utf-8"))
        candidates_total = int(data.get("candidates_total", 0))
        rejections = data.get("rejections_by_reason") or {}
        duplicate_count = int(rejections.get("duplicate_question", 0))

    feedback = load_duplicate_feedback(bundle_root)
    if feedback and candidates_total == 0:
        candidates_total = len(feedback)

    duplicate_rate = duplicate_count / candidates_total if candidates_total else 0.0

    dev_path = bundle_root / "items" / "dev.jsonl"
    by_profile: dict[str, ProfileDiversityStats] = {}
    if dev_path.is_file():
        items = load_dev_split_items(dev_path)
        issuers_by_profile: dict[str, set[str]] = {}
        tags_by_profile: dict[str, set[str]] = {}
        counts: dict[str, int] = {}
        sampling_path = bundle_root / "sampling_manifest.json"
        acc_to_ticker: dict[str, str] = {}
        if sampling_path.is_file():
            manifest = json.loads(sampling_path.read_text(encoding="utf-8"))
            for issuer in manifest.get("selected_issuers", []):
                ticker = issuer.get("ticker", "")
                for acc in issuer.get("accessions") or []:
                    acc_to_ticker[str(acc)] = str(ticker)

        for item in items:
            profile = item.inspiration_profile
            counts[profile] = counts.get(profile, 0) + 1
            tags_by_profile.setdefault(profile, set()).add(item.question_type_tag)
            accs = item.expected_bindings.accessions or []
            ticker = acc_to_ticker.get(accs[0], accs[0][:8] if accs else "unknown")
            issuers_by_profile.setdefault(profile, set()).add(ticker)

        for profile, count in counts.items():
            by_profile[profile] = ProfileDiversityStats(
                unique_issuers=len(issuers_by_profile.get(profile, set())),
                unique_question_type_tags=len(tags_by_profile.get(profile, set())),
                items_accepted=count,
            )

    return DiversityReport(
        duplicate_rejection_rate=duplicate_rate,
        duplicate_rejection_count=duplicate_count,
        candidates_total=candidates_total,
        by_profile=by_profile,
        baseline_reference=baseline_reference,
    )


def write_diversity_report(bundle_root: Path, *, baseline_reference: str = "v2.0.0") -> Path:
    report = build_diversity_report(bundle_root, baseline_reference=baseline_reference)
    path = bundle_root / "diversity_report.json"
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
