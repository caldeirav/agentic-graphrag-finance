"""Unit tests for quality pass summary (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.quality_summary import build_quality_pass_summary
from models.benchmark_generation import CorpusSpotCheckStatus, FailureClass
from models.evaluation import BenchmarkResult, RankingMetrics


def _draft_with_item(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    row = {
        "item_id": "v2-financebench-0001",
        "question": "Q",
        "question_type_tag": "cross-filing-comparison",
        "inspiration_profile": "finagentbench",
        "ground_truth": {"answer": "Both discuss risk."},
        "expected_bindings": {"accessions": ["a", "b"]},
        "expected_section_paths": ["a/Item1A", "b/Item1A"],
        "validation_status": "accepted",
    }
    (draft / "items" / "dev.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return draft


def test_quality_summary_failure_class_counts(tmp_path: Path) -> None:
    draft = _draft_with_item(tmp_path)
    append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="alice",
        failure_class=FailureClass.GT_BOILERPLATE,
    )
    summary = build_quality_pass_summary(draft)
    assert summary.items_reviewed == 1
    assert summary.failure_class_counts["gt_boilerplate"] == 1


def test_quality_summary_dataset_caused_zero_score(tmp_path: Path) -> None:
    draft = _draft_with_item(tmp_path)
    append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="alice",
        failure_class=FailureClass.GT_TOO_STRICT,
    )
    repro = tmp_path / "repro"
    (repro / "graph-full").mkdir(parents=True)
    results = [
        BenchmarkResult(
            item_id="v2-financebench-0001",
            outcome_score=0.0,
            ranking_metrics=RankingMetrics(mrr=0.6, ndcg_at_10=0.2),
        ).model_dump(mode="json"),
    ]
    (repro / "graph-full" / "results.json").write_text(json.dumps(results) + "\n", encoding="utf-8")
    summary = build_quality_pass_summary(draft, repro_input=repro)
    assert summary.dataset_caused_zero_score_count == 1
    assert summary.dataset_caused_zero_score_rate == 1.0
