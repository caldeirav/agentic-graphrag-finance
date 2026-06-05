"""Unit tests for headline pivot layout (014)."""

from pathlib import Path

from evaluation.reproduction.report_formatters import pivot_headline_table
from evaluation.reproduction.report_loader import load_repro_report_bundle
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_pivot_headline_variants_as_rows(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    columns, rows = pivot_headline_table(bundle.tables["headline"].rows)
    assert columns[0] == "variant_id"
    assert "outcome_accuracy" in columns
    assert "ndcg_at_10" in columns
    assert len(rows) == 2
    graph_full = next(r for r in rows if r["variant_id"] == "graph-full")
    assert graph_full["outcome_accuracy"] != "—"
    assert "metric_name" not in columns
