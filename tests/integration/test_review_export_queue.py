"""Integration test for review queue export (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.queue import build_review_queue, write_review_queue
from models.evaluation import BenchmarkResult, RankingMetrics


def test_export_queue_integration(tmp_path: Path) -> None:
    draft = tmp_path / "bundle"
    (draft / "items").mkdir(parents=True)
    (draft / "manifest.json").write_text(json.dumps({"version": "2.0.0"}) + "\n", encoding="utf-8")
    dev_rows = []
    for idx in range(3):
        dev_rows.append(
            {
                "item_id": f"v2-financebench-{idx:04d}",
                "question": f"Question {idx}?",
                "question_type_tag": "metrics",
                "inspiration_profile": "financebench",
                "ground_truth": {"answer": str(idx)},
                "expected_bindings": {"accessions": ["acc-1"]},
                "expected_section_paths": ["acc-1/Item7"],
                "validation_status": "accepted",
            }
        )
    (draft / "items" / "dev.jsonl").write_text(
        "\n".join(json.dumps(r) for r in dev_rows) + "\n",
        encoding="utf-8",
    )

    repro = tmp_path / "repro"
    variant = repro / "graph-full"
    variant.mkdir(parents=True)
    results = [
        BenchmarkResult(
            item_id="v2-financebench-0000",
            outcome_score=0.0,
            ranking_metrics=RankingMetrics(mrr=0.55, ndcg_at_10=0.1),
        ).model_dump(mode="json"),
        BenchmarkResult(
            item_id="v2-financebench-0001",
            outcome_score=0.0,
            ranking_metrics=RankingMetrics(mrr=0.1, ndcg_at_10=0.1),
        ).model_dump(mode="json"),
        BenchmarkResult(
            item_id="v2-financebench-0002",
            outcome_score=0.8,
            ranking_metrics=RankingMetrics(mrr=0.9, ndcg_at_10=0.9),
        ).model_dump(mode="json"),
    ]
    (variant / "results.json").write_text(json.dumps(results) + "\n", encoding="utf-8")

    entries = build_review_queue(draft, repro_input=repro, variant="graph-full", tier_filter=1)
    assert len(entries) == 1
    assert entries[0].item_id == "v2-financebench-0000"

    json_path, csv_path = write_review_queue(
        draft,
        build_review_queue(draft, repro_input=repro),
        draft / "review_queue",
        repro_input=repro,
    )
    assert json_path.is_file()
    assert csv_path.is_file()
    envelope = json.loads(json_path.read_text(encoding="utf-8"))
    assert envelope["tier_counts"]["1"] == 1
