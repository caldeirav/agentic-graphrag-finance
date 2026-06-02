"""Unit tests for run summary and variant comparison (014)."""

from pathlib import Path

from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_render import build_run_summary, build_variant_comparison
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_run_summary_fields(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    summary = build_run_summary(bundle)
    assert summary.release_tag == "paper-smoke"
    assert summary.duration_seconds is not None
    assert len(summary.variant_counts) >= 2
    assert summary.export_manifest_summary is not None


def test_variant_comparison_primary_metrics(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    comparison = build_variant_comparison(bundle)
    assert "outcome_accuracy" in comparison.metric_names
    ids = [s.variant_id for s in comparison.series]
    assert "graph-full" in ids
    assert "flat-chunk" in ids
