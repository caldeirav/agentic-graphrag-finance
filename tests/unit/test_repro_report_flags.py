"""Unit tests for investigation flags (014)."""

from pathlib import Path

from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_render import _binding_miss, compute_investigation_flags
from evaluation.reproduction.report_models import ItemResultRecord
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_binding_miss_empty_citations_ok_status() -> None:
    record = ItemResultRecord(
        variant_id="graph-full",
        item_id="x",
        judge_status="ok",
        validation_status="complete",
        citation_count=0,
        flags=["ok"],
    )
    assert _binding_miss(record) is True


def test_high_delta_vs_graph_full(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    compute_investigation_flags(bundle, delta_threshold=0.10)
    flat = bundle.variant_results["flat-chunk"][0]
    assert "high_delta" in flat.flags


def test_no_high_delta_on_baseline(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    compute_investigation_flags(bundle, delta_threshold=0.10)
    base = bundle.variant_results["graph-full"][0]
    assert "high_delta" not in base.flags
