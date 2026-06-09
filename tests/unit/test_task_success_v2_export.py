"""Unit tests for task_success v2.0 export semantics (017)."""

from evaluation.reproduction.export import build_variant_summary, export_paper_tables
from models.evaluation import BenchmarkResult, RankingMetrics


def _result(item_id: str, *, outcome: float | None = 1.0, rubric: float = 0.5) -> BenchmarkResult:
    return BenchmarkResult(
        item_id=item_id,
        validation_status="complete",
        judge_status="ok",
        outcome_score=outcome if outcome is not None else 0.0,
        alignment_score=rubric,
        trajectory_fidelity=0.9,
        ranking_metrics=RankingMetrics(mrr=0.5, map_score=0.4, ndcg_at_10=0.6),
    )


def _ground_truth(*, answer: str | None = "42", rubric: str | None = None) -> dict:
    gt: dict = {}
    if answer is not None:
        gt["answer"] = answer
    if rubric is not None:
        gt["rubric"] = rubric
    return gt


def test_v2_task_success_mean_va_over_full_n() -> None:
    n = 200
    results = [_result(f"v2-item-{i:03d}", outcome=0.5 + (i % 2) * 0.5) for i in range(n)]
    profiles = {r.item_id: "financebench" for r in results}
    relevance = {r.item_id: ["c1"] for r in results}
    gt = {r.item_id: _ground_truth() for r in results}
    summary = build_variant_summary("graph-full", results, profiles, relevance, gt)
    export = export_paper_tables(
        [summary],
        release_tag="paper-v2.0",
        custom_judge_version="2.0.0",
    )
    task = next(r for r in export.headline_rows if r.metric_name == "task_success")
    assert task.item_count == n
    assert task.value == 0.75
    rubric_rows = [r for r in export.headline_rows if r.metric_name == "rubric_alignment"]
    assert rubric_rows == []


def test_v2_missing_va_counts_as_zero() -> None:
    results = [_result(f"v2-item-{i:03d}", outcome=1.0 if i < 195 else None) for i in range(200)]
    profiles = {r.item_id: "financebench" for r in results}
    relevance = {r.item_id: ["c1"] for r in results}
    gt = {r.item_id: _ground_truth() for r in results}
    summary = build_variant_summary("graph-full", results, profiles, relevance, gt)
    export = export_paper_tables(
        [summary],
        release_tag="paper-v2.0",
        custom_judge_version="2.0.0",
    )
    task = next(r for r in export.headline_rows if r.metric_name == "task_success")
    assert task.item_count == 200
    assert task.value == 0.975


def test_v1_backward_compat_keeps_rubric_alignment() -> None:
    results = [
        _result("a1", outcome=1.0, rubric=0.0),
        _result("r1", outcome=0.5, rubric=0.6),
    ]
    profiles = {"a1": "financebench", "r1": "finder"}
    relevance = {"a1": ["c1"], "r1": ["c2"]}
    gt = {"a1": _ground_truth(), "r1": _ground_truth(answer=None, rubric="only rubric")}
    summary = build_variant_summary("graph-full", results, profiles, relevance, gt)
    export = export_paper_tables(
        [summary],
        release_tag="paper-v1.0",
        custom_judge_version="1.2.0",
    )
    rubric = next(r for r in export.headline_rows if r.metric_name == "rubric_alignment")
    assert rubric.item_count == 2
    task = next(r for r in export.headline_rows if r.metric_name == "task_success")
    assert task.value == 0.8
