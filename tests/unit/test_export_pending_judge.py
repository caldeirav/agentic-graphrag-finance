"""Export excludes pending judge rows from headline aggregates (013)."""

from __future__ import annotations

from evaluation.reproduction.export import build_variant_summary, export_paper_tables
from models.evaluation import BenchmarkResult


def test_pending_rows_excluded_from_headline() -> None:
    results = [
        BenchmarkResult(item_id="a", judge_status="ok", outcome_score=1.0),
        BenchmarkResult(item_id="b", judge_status="pending", outcome_score=0.5),
    ]
    summary = build_variant_summary(
        "graph-full",
        results,
        {"a": "financebench", "b": "financebench"},
        {"a": [], "b": []},
        {"a": {"answer": "x"}, "b": {"answer": "y"}},
    )
    assert summary.excluded_pending_judge == 1
    export = export_paper_tables([summary], release_tag="test")
    row = next(r for r in export.headline_rows if r.metric_name == "outcome_accuracy")
    assert row.item_count == 1
