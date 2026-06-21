"""Cohort validation gate for paper-v1.1 reproduction (019)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from evaluation.generation.review.queue import _load_repro_results, _outcome_score, _ranking_values
from evaluation.reproduction.investigation.pack import build_failure_investigation_rows
from evaluation.reproduction.investigation.taxonomy import (
    is_strong_retrieval_zero_outcome,
    rollup_engineering_counts,
)
from evaluation.reproduction.smoke_gate import _mrr, _value_alignment
from models.investigation import (
    CohortBaselineComparison,
    CohortGateOverrideRecord,
    CohortGateThresholds,
    CohortValidationReport,
    Tier1CohortFile,
)


def load_cohort_gate_thresholds(manifest: dict) -> CohortGateThresholds:
    raw = manifest.get("cohort_gate_thresholds") or {}
    return CohortGateThresholds.model_validate(raw)


def load_cohort_validation_report(path: Path) -> CohortValidationReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CohortValidationReport.model_validate(payload)


def _cohort_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthesis_path_from_result(row) -> str:
    snap = row.trajectory_snapshot or {}
    if isinstance(snap, dict):
        return str(snap.get("synthesis_path") or "unknown")
    return "unknown"


def run_regression_suite() -> bool:
    repo_root = Path(__file__).resolve().parents[4]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/regression/failure_modes",
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    return proc.returncode == 0


def build_cohort_validation_report(
    *,
    cohort: Tier1CohortFile,
    cohort_path: Path,
    output_dir: Path,
    manifest: dict,
    draft: Path,
    repro_input: Path,
    variant: str = "graph-full",
    baseline_report_path: Path | None = None,
    skip_regression_check: bool = False,
) -> CohortValidationReport:
    thresholds = load_cohort_gate_thresholds(manifest)
    results = _load_repro_results(repro_input, variant)
    rows = build_failure_investigation_rows(
        draft,
        repro_input=repro_input,
        variant=variant,
        item_ids=cohort.item_ids,
    )

    tier1_zero = 0
    strong_zero = 0
    mrr_ok_va_zero = 0
    synthesis_counts: dict[str, int] = {}
    engineering_classes = []

    for item_id in cohort.item_ids:
        result = results.get(item_id)
        if result is None:
            continue
        outcome = _outcome_score(result)
        mrr_val, ndcg = _ranking_values(result)
        if outcome <= 0:
            tier1_zero += 1
        if is_strong_retrieval_zero_outcome(
            outcome_score=outcome,
            mrr=mrr_val,
            ndcg_at_10=ndcg,
        ):
            strong_zero += 1
        va = _value_alignment(result)
        if _mrr(result) >= 0.5 and va == 0.0:
            mrr_ok_va_zero += 1
        path = _synthesis_path_from_result(result)
        synthesis_counts[path] = synthesis_counts.get(path, 0) + 1

    for row in rows:
        engineering_classes.append(row.suggested_failure_class)

    baseline_comparison: CohortBaselineComparison | None = None
    if baseline_report_path and baseline_report_path.is_file():
        baseline = load_cohort_validation_report(baseline_report_path)
        delta = strong_zero - baseline.strong_retrieval_zero_count
        pct = 0.0
        if baseline.strong_retrieval_zero_count:
            pct = (delta / baseline.strong_retrieval_zero_count) * 100.0
        baseline_comparison = CohortBaselineComparison(
            baseline_strong_retrieval_zero_count=baseline.strong_retrieval_zero_count,
            delta_strong_retrieval_zero_count=delta,
            delta_percent=pct,
        )

    regression_passed: bool | None = None
    if thresholds.require_regression_suite_pass and not skip_regression_check:
        regression_passed = run_regression_suite()

    failed: list[str] = []
    if strong_zero > thresholds.max_strong_retrieval_zero_outcome:
        failed.append(
            f"strong_retrieval_zero_outcome {strong_zero} > max {thresholds.max_strong_retrieval_zero_outcome}"
        )
    if mrr_ok_va_zero > thresholds.max_mrr_ok_va_zero:
        failed.append(f"mrr_ok_va_zero {mrr_ok_va_zero} > max {thresholds.max_mrr_ok_va_zero}")
    if baseline_comparison and baseline_report_path and baseline_report_path.is_file():
        baseline = load_cohort_validation_report(baseline_report_path)
        baseline_template_share = 0.0
        total = sum(baseline.synthesis_path_counts.values()) or 1
        baseline_template_share = baseline.synthesis_path_counts.get("template", 0) / total
        current_total = sum(synthesis_counts.values()) or 1
        current_template_share = synthesis_counts.get("template", 0) / current_total
        reduction = baseline_template_share - current_template_share
        if reduction < thresholds.min_synthesis_template_dump_share_reduction:
            failed.append(
                "synthesis_template_dump_share_reduction "
                f"{reduction:.3f} < min {thresholds.min_synthesis_template_dump_share_reduction}"
            )
    if regression_passed is False:
        failed.append("failure_mode_regression_suite_failed")

    report = CohortValidationReport(
        cohort_hash=_cohort_hash(cohort_path),
        manifest_tag=str(manifest.get("release_tag") or ""),
        run_at=datetime.now(UTC),
        output_dir=str(output_dir),
        item_count=len(cohort.item_ids),
        tier1_zero_count=tier1_zero,
        strong_retrieval_zero_count=strong_zero,
        synthesis_path_counts=synthesis_counts,
        engineering_failure_counts=rollup_engineering_counts(engineering_classes),
        mrr_ok_va_zero_count=mrr_ok_va_zero,
        thresholds=thresholds,
        baseline_comparison=baseline_comparison,
        passed=len(failed) == 0,
        failed_thresholds=failed,
        regression_suite_passed=regression_passed,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "cohort_validation_report.json"
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def check_cohort_gate_for_run_all(
    manifest: dict,
    *,
    cohort_report_path: Path | None = None,
) -> CohortValidationReport:
    thresholds = load_cohort_gate_thresholds(manifest)
    report_path = cohort_report_path
    if report_path is None and thresholds.baseline_snapshot_path:
        candidate = Path(thresholds.baseline_snapshot_path)
        if not candidate.is_absolute():
            repo_root = Path(__file__).resolve().parents[4]
            candidate = repo_root / candidate
        report_path = candidate
    if report_path is None or not report_path.is_file():
        msg = f"Cohort validation report not found: {report_path}"
        raise FileNotFoundError(msg)
    report = load_cohort_validation_report(report_path)
    if not report.passed:
        msg = "Cohort gate failed: " + "; ".join(report.failed_thresholds)
        raise RuntimeError(msg)
    return report


def append_cohort_gate_override(
    output_dir: Path,
    *,
    manifest_tag: str,
    failed_thresholds: list[str],
    rationale: str,
    operator: str = "",
) -> Path:
    import os

    record = CohortGateOverrideRecord(
        operator=operator or os.environ.get("USER", "unknown"),
        manifest_tag=manifest_tag,
        failed_thresholds=failed_thresholds,
        rationale=rationale,
    )
    path = output_dir / "cohort_gate_overrides.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return path
