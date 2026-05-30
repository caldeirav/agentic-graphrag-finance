"""Contract test: paper table CSV schema (012)."""

import csv
from pathlib import Path

from evaluation.reproduction.export import build_variant_summary, export_paper_tables, write_paper_tables
from models.evaluation import BenchmarkResult, RankingMetrics


def test_paper_table_csv_columns_match_contract(tmp_path: Path) -> None:
    result = BenchmarkResult(
        item_id="i1",
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.9,
        alignment_score=0.8,
        trajectory_fidelity=0.7,
        ranking_metrics=RankingMetrics(mrr=0.5, map_score=0.4, ndcg_at_10=0.6),
    )
    summary = build_variant_summary(
        "graph-full",
        [result],
        profiles_by_item={"i1": "financebench"},
        relevance_by_item={"i1": ["c1"]},
        ground_truth_by_item={"i1": {"answer": "a", "rubric": "r"}},
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    write_paper_tables(export, tmp_path)
    tables = tmp_path / "tables"

    headline_fields = [
        "variant_id",
        "metric_name",
        "value",
        "item_count",
        "excluded_incomplete",
        "excluded_degraded",
        "na_reason",
    ]
    with (tables / "headline.csv").open(encoding="utf-8") as fh:
        assert csv.DictReader(fh).fieldnames == headline_fields

    by_profile_fields = [
        "variant_id",
        "inspiration_profile",
        "metric_name",
        "value",
        "item_count",
        "excluded_incomplete",
        "excluded_degraded",
        "na_reason",
    ]
    with (tables / "by_profile.csv").open(encoding="utf-8") as fh:
        assert csv.DictReader(fh).fieldnames == by_profile_fields

    with (tables / "variant_delta.csv").open(encoding="utf-8") as fh:
        assert csv.DictReader(fh).fieldnames == [
            "baseline_variant",
            "comparison_variant",
            "metric_name",
            "delta",
        ]

    with (tables / "trajectory_audit.csv").open(encoding="utf-8") as fh:
        assert csv.DictReader(fh).fieldnames == [
            "variant_id",
            "excluded_incomplete",
            "excluded_degraded",
            "included_in_headline",
        ]
