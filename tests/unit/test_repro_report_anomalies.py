"""Unit tests for repro report anomaly detection (014)."""

from pathlib import Path

from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_render import detect_run_anomalies
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_detects_small_sample_and_zero_rubric(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    anomalies = detect_run_anomalies(bundle)
    messages = " ".join(a.message for a in anomalies)
    assert "Small benchmark sample" in messages or "n=2" in messages
    assert "Rubric alignment is 0.0" in messages


def test_detects_duplicate_variant_runs(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    import json

    repro = json.loads((tmp_path / "repro_run.json").read_text())
    repro["variant_runs"] = repro["variant_runs"] + repro["variant_runs"]
    (tmp_path / "repro_run.json").write_text(json.dumps(repro))
    bundle = load_repro_report_bundle(tmp_path)
    anomalies = detect_run_anomalies(bundle)
    assert any("duplicate variant_runs" in a.message for a in anomalies)
