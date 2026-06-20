"""Unit tests for review queue export (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.queue import assign_priority_tier, build_review_queue
from models.evaluation import BenchmarkResult, RankingMetrics


def test_assign_priority_tier_one_high_retrieval_zero_outcome():
    tier, score = assign_priority_tier(outcome_score=0.0, mrr=0.75, ndcg_at_10=0.1)
    assert tier == 1
    assert score == 0.75


def test_assign_priority_tier_two_zero_outcome_low_retrieval():
    tier, score = assign_priority_tier(outcome_score=0.0, mrr=0.1, ndcg_at_10=0.1)
    assert tier == 2
    assert score == 0.1


def test_assign_priority_tier_three_positive_outcome():
    tier, score = assign_priority_tier(outcome_score=0.5, mrr=0.9, ndcg_at_10=0.9)
    assert tier == 3
    assert score == 0.0


def test_build_review_queue_sort_order(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    items_dir = draft / "items"
    items_dir.mkdir(parents=True)
    (draft / "manifest.json").write_text(
        json.dumps({"version": "2.0.0-draft"}) + "\n",
        encoding="utf-8",
    )
    rows = [
        {
            "item_id": "v2-financebench-0001",
            "question": "Q1",
            "question_type_tag": "metrics",
            "inspiration_profile": "financebench",
            "ground_truth": {"answer": "1"},
            "expected_bindings": {"accessions": ["acc-1"]},
            "expected_section_paths": ["acc-1/Item7"],
            "validation_status": "accepted",
        },
        {
            "item_id": "v2-financebench-0002",
            "question": "Q2",
            "question_type_tag": "metrics",
            "inspiration_profile": "financebench",
            "ground_truth": {"answer": "2"},
            "expected_bindings": {"accessions": ["acc-1"]},
            "expected_section_paths": ["acc-1/Item7"],
            "validation_status": "accepted",
        },
    ]
    (items_dir / "dev.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )

    repro = tmp_path / "repro"
    variant_dir = repro / "graph-full"
    variant_dir.mkdir(parents=True)
    results = [
        BenchmarkResult(
            item_id="v2-financebench-0001",
            outcome_score=0.0,
            ranking_metrics=RankingMetrics(mrr=0.6, ndcg_at_10=0.2),
        ).model_dump(mode="json"),
        BenchmarkResult(
            item_id="v2-financebench-0002",
            outcome_score=0.0,
            ranking_metrics=RankingMetrics(mrr=0.2, ndcg_at_10=0.1),
        ).model_dump(mode="json"),
    ]
    (variant_dir / "results.json").write_text(json.dumps(results) + "\n", encoding="utf-8")

    entries = build_review_queue(draft, repro_input=repro, variant="graph-full")
    assert entries[0].item_id == "v2-financebench-0001"
    assert entries[0].priority_tier == 1
    assert entries[1].priority_tier == 2


def test_build_review_queue_missing_repro_tier_three(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    items_dir = draft / "items"
    items_dir.mkdir(parents=True)
    row = {
        "item_id": "v2-financebench-0001",
        "question": "Q1",
        "question_type_tag": "metrics",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "1"},
        "expected_bindings": {"accessions": ["acc-1"]},
        "expected_section_paths": ["acc-1/Item7"],
        "validation_status": "accepted",
    }
    (items_dir / "dev.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    entries = build_review_queue(draft, repro_input=None)
    assert len(entries) == 1
    assert entries[0].priority_tier == 3
    assert entries[0].mrr is None
