"""Integration assertion for SC-002 ranking stability (016)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.export import build_variant_summary, export_paper_tables
from models.evaluation import BenchmarkResult, JudgeVerdict


def test_ranking_delta_below_threshold_on_fixed_checkpoints(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/repro/paper-smoke/graph-full/results.json")
    if not fixture.is_file():
        return
    rows = json.loads(fixture.read_text(encoding="utf-8"))
    results = [BenchmarkResult.model_validate(r) for r in rows]
    profiles = {r.item_id: "financebench" for r in results}
    relevance = {r.item_id: ["c1"] for r in results}
    ground_truth = {r.item_id: {"answer": "x"} for r in results}

    baseline = export_paper_tables(
        [
            build_variant_summary(
                "graph-full",
                results,
                profiles,
                relevance,
                ground_truth,
            )
        ],
        release_tag="sc002-baseline",
    )
    mutated = []
    for r in results:
        mutated.append(
            r.model_copy(
                update={
                    "outcome_score": 0.0,
                    "judge_verdict": JudgeVerdict(
                        judge_model="gemini",
                        judge_version="v3",
                        scores={"value_alignment": 0.0, "synthesis_grounding": 0.0},
                    ),
                }
            )
        )
    after = export_paper_tables(
        [
            build_variant_summary(
                "graph-full",
                mutated,
                profiles,
                relevance,
                ground_truth,
            )
        ],
        release_tag="sc002-after",
    )

    def _metric(export, name: str) -> float:
        for row in export.headline_rows:
            if row.metric_name == name and not row.na_reason:
                return row.value
        return 0.0

    for metric in ("mrr", "map", "ndcg_at_10"):
        delta = abs(_metric(baseline, metric) - _metric(after, metric))
        assert delta < 0.001, f"{metric} delta {delta} exceeds SC-002 threshold"
