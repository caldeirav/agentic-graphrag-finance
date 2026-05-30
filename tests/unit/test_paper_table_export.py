"""Unit tests for paper table export (012)."""

from pathlib import Path

from evaluation.reproduction.export import (
    build_variant_summary,
    export_paper_tables,
    write_paper_tables,
)
from models.evaluation import BenchmarkResult, RankingMetrics


def _result(
    item_id: str,
    *,
    validation_status: str = "complete",
    judge_status: str = "ok",
    outcome: float = 1.0,
    rubric: float = 0.8,
    fidelity: float = 0.9,
    mrr: float = 0.5,
) -> BenchmarkResult:
    return BenchmarkResult(
        item_id=item_id,
        validation_status=validation_status,
        judge_status=judge_status,
        outcome_score=outcome,
        alignment_score=rubric,
        trajectory_fidelity=fidelity,
        ranking_metrics=RankingMetrics(mrr=mrr, map_score=0.4, ndcg_at_10=0.6),
    )


def test_excludes_incomplete_from_headline_means() -> None:
    results = [
        _result("ok1", outcome=1.0),
        _result("bad", validation_status="incomplete", outcome=0.0),
    ]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"ok1": "financebench", "bad": "financebench"},
        relevance_by_item={"ok1": ["c1"], "bad": ["c2"]},
        ground_truth_by_item={
            "ok1": {"answer": "a", "rubric": "r"},
            "bad": {"answer": "b", "rubric": "r"},
        },
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    outcome_rows = [r for r in export.headline_rows if r.metric_name == "outcome_accuracy"]
    assert len(outcome_rows) == 1
    assert outcome_rows[0].value == 1.0
    assert outcome_rows[0].excluded_incomplete == 1


def test_excludes_degraded_from_headline_means() -> None:
    results = [
        _result("ok1", outcome=1.0),
        _result("deg", judge_status="degraded", outcome=0.0),
    ]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"ok1": "finder", "deg": "finder"},
        relevance_by_item={"ok1": ["c1"], "deg": ["c2"]},
        ground_truth_by_item={
            "ok1": {"answer": "a", "rubric": "r"},
            "deg": {"answer": "b", "rubric": "r"},
        },
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    outcome_rows = [r for r in export.headline_rows if r.metric_name == "outcome_accuracy"]
    assert outcome_rows[0].value == 1.0
    assert outcome_rows[0].excluded_degraded == 1


def test_finder_profile_marks_rubric_only_outcome() -> None:
    results = [_result("f1")]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"f1": "finder"},
        relevance_by_item={"f1": ["c1"]},
        ground_truth_by_item={"f1": {"rubric": "only rubric"}},
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    finder_outcome = [
        r
        for r in export.by_profile_rows
        if r.inspiration_profile == "finder" and r.metric_name == "outcome_accuracy"
    ]
    assert finder_outcome[0].na_reason == "rubric_only"


def test_writes_headline_tex(tmp_path: Path) -> None:
    results = [_result("i1")]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"i1": "financebench"},
        relevance_by_item={"i1": ["c1"]},
        ground_truth_by_item={"i1": {"answer": "a", "rubric": "r"}},
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    write_paper_tables(export, tmp_path)
    tex = (tmp_path / "tables" / "headline.tex").read_text(encoding="utf-8")
    assert "\\begin{tabular}" in tex
    assert "graph-full" in tex
