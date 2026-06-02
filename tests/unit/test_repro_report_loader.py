"""Unit tests for repro report loader (014)."""

from pathlib import Path

import pytest

from evaluation.reproduction.report_errors import ReportInputError
from evaluation.reproduction.report_loader import load_repro_report_bundle
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_load_required_files(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    assert bundle.repro_run.release_tag == "paper-smoke"
    assert "headline" in bundle.tables
    assert "graph-full" in bundle.variant_results


def test_missing_repro_run_fails(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    (tmp_path / "repro_run.json").unlink()
    with pytest.raises(ReportInputError, match="repro_run.json"):
        load_repro_report_bundle(tmp_path)


def test_bad_csv_header_fails(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path, bad_csv_header=True)
    with pytest.raises(ReportInputError, match="header mismatch"):
        load_repro_report_bundle(tmp_path)


def test_partial_variant_results_warning_not_fail(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path, omit_variant="flat-chunk")
    bundle = load_repro_report_bundle(tmp_path)
    assert "flat-chunk" in bundle.incomplete_variants
    assert any("flat-chunk" in w for w in bundle.warnings)
    assert "graph-full" in bundle.variant_results


def test_optional_files_warn_when_missing(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    (tmp_path / "export_manifest.json").unlink()
    (tmp_path / "tables" / "headline.tex").unlink()
    bundle = load_repro_report_bundle(tmp_path)
    assert bundle.export_manifest is None
    assert bundle.headline_tex is None
    assert any("export_manifest" in w for w in bundle.warnings)
