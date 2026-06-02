"""Unit tests for item drill-down mapping (014)."""

from pathlib import Path

from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_render import _status_class, compute_investigation_flags
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_item_records_mapped(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    records = bundle.variant_results["graph-full"]
    assert len(records) == 2
    by_id = {r.item_id: r for r in records}
    assert by_id["item-1"].judge_status == "ok"
    assert by_id["item-1"].citation_count == 0
    assert by_id["item-2"].judge_status == "degraded"


def test_status_highlight_classes() -> None:
    assert _status_class("degraded") == "status-degraded"
    assert _status_class("pending") == "status-pending"
    assert _status_class("not_evaluable") == "status-not_evaluable"


def test_high_delta_flag(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    compute_investigation_flags(bundle, delta_threshold=0.05)
    flat = {r.item_id: r for r in bundle.variant_results["flat-chunk"]}
    assert "high_delta" in flat["item-1"].flags
