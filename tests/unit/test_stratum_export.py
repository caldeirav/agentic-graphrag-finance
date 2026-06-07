"""Unit tests for stratified table export (015)."""

from evaluation.reproduction.export import build_variant_summary, export_paper_tables
from models.evaluation import BenchmarkResult, RankingMetrics
from models.query import AnswerPackage


def _result(item_id: str, *, abstain: bool = False) -> BenchmarkResult:
    if abstain:
        answer = AnswerPackage(text="Insufficient evidence to answer.", citations=[])
    else:
        answer = AnswerPackage(
            text="answer",
            citations=[],
        )
    return BenchmarkResult(
        item_id=item_id,
        answer=answer,
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.5,
        alignment_score=0.4,
        trajectory_fidelity=0.9,
        ranking_metrics=RankingMetrics(mrr=0.2, map_score=0.1, ndcg_at_10=0.15),
    )


def test_by_evidence_source_csv_rows() -> None:
    results = [_result("html-item"), _result("xbrl-item")]
    profiles = {"html-item": "financebench", "xbrl-item": "financebench"}
    relevance = {
        "html-item": ["doc-a-html-risk-1"],
        "xbrl-item": ["doc-a-xbrl-rev"],
    }
    gt = {"html-item": {"answer": "1"}, "xbrl-item": {"answer": "2"}}
    summary = build_variant_summary("graph-full", results, profiles, relevance, gt)
    export = export_paper_tables(
        [summary],
        release_tag="paper-test",
        relevance_by_item=relevance,
    )
    assert export.by_evidence_source_rows
    strata = {r.primary_evidence_source for r in export.by_evidence_source_rows}
    assert "html" in strata
    assert "xbrl" in strata
    assert export.stratum_audit.get("unknown_excluded", 0) == 0


def test_abstention_rate_computed() -> None:
    results = [_result("i1", abstain=True), _result("i2", abstain=False)]
    relevance = {"i1": ["doc-a-html-a"], "i2": ["doc-a-html-b"]}
    summary = build_variant_summary(
        "ablation-no-walker",
        results,
        {"i1": "fb", "i2": "fb"},
        relevance,
        {"i1": {"answer": "x"}, "i2": {"answer": "y"}},
    )
    export = export_paper_tables(
        [summary],
        release_tag="paper-test",
        relevance_by_item=relevance,
    )
    abst_rows = [
        r for r in export.by_evidence_source_rows
        if r.metric_name == "abstention_rate" and r.primary_evidence_source == "html"
    ]
    assert abst_rows
    assert abst_rows[0].value == 0.5
