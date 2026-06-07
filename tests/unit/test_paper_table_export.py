"""Unit tests for paper table export (012)."""

import json
from pathlib import Path

from evaluation.reproduction.export import (
    build_variant_summary,
    export_paper_tables,
    export_tables_from_disk,
    write_paper_tables,
)
from models.evaluation import BenchmarkResult, RankingMetrics
from models.reproduction import ModelPins, ReleaseManifest


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


def test_profile_without_answer_gt_marks_outcome_na() -> None:
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
    assert finder_outcome[0].na_reason == "no_answer_gt"
    assert finder_outcome[0].item_count == 0


def test_headline_outcome_item_count_is_answer_gt_only() -> None:
    results = [
        _result("a1", outcome=1.0),
        _result("r1", outcome=0.5),
    ]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"a1": "financebench", "r1": "finder"},
        relevance_by_item={"a1": ["c1"], "r1": ["c2"]},
        ground_truth_by_item={"a1": {"answer": "42"}, "r1": {"rubric": "only rubric"}},
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    outcome = next(r for r in export.headline_rows if r.metric_name == "outcome_accuracy")
    assert outcome.item_count == 1
    assert outcome.value == 1.0


def _test_manifest(bundle_path: str = "bundle") -> ReleaseManifest:
    return ReleaseManifest(
        release_tag="test",
        git_sha="sha",
        custom_judge_version="1.0.0",
        custom_judge_bundle_path=bundle_path,
        eval_split="dev",
        variant_ids=["graph-full"],
        model_pins=ModelPins(
            llm_config_path="configs/llm/x.yaml",
            llm_config_hash="sha256:x",
            judge_config_path="configs/judges/x.yaml",
            judge_config_hash="sha256:x",
            embedding_model_id="sentence-transformers/all-MiniLM-L6-v2",
            embedding_model_revision="rev",
            embedding_config_path="configs/reproduction/embeddings/x.yaml",
            embedding_config_hash="sha256:x",
        ),
    )


def test_export_manifest_records_custom_judge_version(tmp_path: Path) -> None:
    results = [_result("i1")]
    summary = build_variant_summary(
        "graph-full",
        results,
        profiles_by_item={"i1": "financebench"},
        relevance_by_item={"i1": ["c1"]},
        ground_truth_by_item={"i1": {"answer": "a"}},
    )
    export = export_paper_tables([summary], release_tag="paper-smoke")
    export.custom_judge_version = "1.1.0"
    write_paper_tables(export, tmp_path)
    manifest = json.loads((tmp_path / "export_manifest.json").read_text(encoding="utf-8"))
    assert manifest["custom_judge_version"] == "1.1.0"
    assert manifest["min_judge_version"] == "v3"
    assert manifest["outcome_scoring_policy"] == "value_alignment_only"


def test_export_tables_from_disk_loads_item_context(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "items").mkdir(parents=True)
    item = {
        "item_id": "i1",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "expected"},
        "relevant_chunk_ids": ["chunk-1"],
    }
    (bundle / "items" / "dev.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")

    out = tmp_path / "out"
    variant_dir = out / "graph-full"
    variant_dir.mkdir(parents=True)
    result = BenchmarkResult(
        item_id="i1",
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.75,
        alignment_score=0.5,
        trajectory_fidelity=0.9,
        ranking_metrics=RankingMetrics(mrr=0.6, map_score=0.4, ndcg_at_10=0.7),
    )
    (variant_dir / "results.json").write_text(
        json.dumps([result.model_dump(mode="json")]),
        encoding="utf-8",
    )

    export = export_tables_from_disk(
        out,
        release_tag="test",
        manifest=_test_manifest(),
        repo_root=tmp_path,
    )
    outcome_rows = [r for r in export.headline_rows if r.metric_name == "outcome_accuracy"]
    assert len(outcome_rows) == 1
    assert outcome_rows[0].value == 0.75
    assert outcome_rows[0].na_reason == ""


def test_export_tables_from_disk_without_manifest_has_no_eligible_items(tmp_path: Path) -> None:
    variant_dir = tmp_path / "graph-full"
    variant_dir.mkdir(parents=True)
    result = BenchmarkResult(
        item_id="i1",
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.75,
        trajectory_fidelity=0.9,
        ranking_metrics=RankingMetrics(mrr=0.6, map_score=0.4, ndcg_at_10=0.7),
    )
    (variant_dir / "results.json").write_text(
        json.dumps([result.model_dump(mode="json")]),
        encoding="utf-8",
    )

    export = export_tables_from_disk(tmp_path, release_tag="test")
    outcome_rows = [r for r in export.headline_rows if r.metric_name == "outcome_accuracy"]
    assert outcome_rows[0].na_reason == "no_eligible_items"


def test_ranking_metrics_unchanged_when_only_outcome_fields_differ() -> None:
    """SC-002: MRR/MAP/nDCG export rows are independent of outcome/judge scores."""
    base_kwargs = {
        "profiles_by_item": {"i1": "financebench"},
        "relevance_by_item": {"i1": ["c1"]},
        "ground_truth_by_item": {"i1": {"answer": "a", "rubric": "r"}},
    }
    ranking = RankingMetrics(mrr=0.42, map_score=0.33, ndcg_at_10=0.51)
    before = _result("i1", outcome=0.9, rubric=0.8, fidelity=0.7, mrr=0.42)
    before = before.model_copy(update={"ranking_metrics": ranking})
    after = before.model_copy(
        update={
            "outcome_score": 0.1,
            "alignment_score": 0.0,
            "trajectory_fidelity": 0.0,
        }
    )
    export_before = export_paper_tables(
        [
            build_variant_summary("graph-full", [before], **base_kwargs),
            build_variant_summary("flat-chunk", [before], **base_kwargs),
        ],
        release_tag="ranking-check",
    )
    export_after = export_paper_tables(
        [
            build_variant_summary("graph-full", [after], **base_kwargs),
            build_variant_summary("flat-chunk", [after], **base_kwargs),
        ],
        release_tag="ranking-check",
    )
    ranking_names = {"mrr", "map", "ndcg_at_10"}

    def _ranking_rows(export):
        return {
            (r.variant_id, r.metric_name): r.value
            for r in export.headline_rows
            if r.metric_name in ranking_names and not r.na_reason
        }

    assert _ranking_rows(export_before) == _ranking_rows(export_after)


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
