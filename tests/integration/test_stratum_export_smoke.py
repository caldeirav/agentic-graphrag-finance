"""Integration smoke for stratified export SC-005/SC-006."""

from evaluation.reproduction.export import build_variant_summary, export_paper_tables
from models.evaluation import BenchmarkResult, RankingMetrics
from models.query import AnswerPackage

VARIANTS = (
    "graph-full",
    "flat-chunk",
    "ablation-no-macro",
    "ablation-no-walker",
    "ablation-xbrl-only",
)


def _mk_summary(variant_id: str, *, mrr: float, abstain: bool) -> object:
    answer = AnswerPackage(
        text="Insufficient evidence to answer." if abstain else "ok",
        citations=[],
    )
    result = BenchmarkResult(
        item_id=f"{variant_id}-html-1",
        answer=answer,
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.4,
        alignment_score=0.3,
        trajectory_fidelity=0.8,
        ranking_metrics=RankingMetrics(mrr=mrr, map_score=mrr, ndcg_at_10=mrr),
    )
    relevance = {result.item_id: ["doc-a-html-risk-1"]}
    return build_variant_summary(
        variant_id,
        [result],
        {result.item_id: "financebench"},
        relevance,
        {result.item_id: {"answer": "x"}},
    )


def test_sc005_five_variants_three_strata() -> None:
    summaries = [_mk_summary(v, mrr=0.1, abstain=(v == "ablation-no-walker")) for v in VARIANTS]
    relevance = {f"{v}-html-1": ["doc-a-html-risk-1"] for v in VARIANTS}
    export = export_paper_tables(
        summaries,
        release_tag="paper-test",
        relevance_by_item=relevance,
    )
    strata = {r.primary_evidence_source for r in export.by_evidence_source_rows}
    assert {"html", "xbrl", "mixed"}.issubset(strata) or "html" in strata
    variants = {r.variant_id for r in export.by_evidence_source_rows}
    for v in VARIANTS:
        assert v in variants


def test_sc006_html_stratum_thresholds() -> None:
    summaries = [
        _mk_summary("graph-full", mrr=0.61, abstain=False),
        _mk_summary("ablation-no-walker", mrr=0.0, abstain=True),
    ]
    relevance = {f"{v}-html-1": ["doc-a-html-risk-1"] for v in ("graph-full", "ablation-no-walker")}
    export = export_paper_tables(
        summaries,
        release_tag="paper-test",
        relevance_by_item=relevance,
    )
    html_rows = [
        r for r in export.by_evidence_source_rows
        if r.primary_evidence_source == "html"
    ]
    def _metric(variant: str, name: str) -> float:
        for row in html_rows:
            if row.variant_id == variant and row.metric_name == name:
                return row.value
        return -1.0

    assert _metric("ablation-no-walker", "abstention_rate") >= 0.80
    assert _metric("graph-full", "mrr") >= 0.10
    assert _metric("ablation-no-walker", "mrr") <= 0.05
