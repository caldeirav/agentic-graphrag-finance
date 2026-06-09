"""Shared fixtures for repro report tests (014)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.reproduction.export import (
    build_variant_summary,
    export_paper_tables,
    write_paper_tables,
)
from models.evaluation import BenchmarkResult, RankingMetrics


def write_minimal_repro_bundle(
    root: Path,
    *,
    include_results: bool = True,
    omit_variant: str | None = None,
    bad_csv_header: bool = False,
) -> Path:
    """Create a minimal valid repro output directory for report tests."""
    root.mkdir(parents=True, exist_ok=True)

    result = BenchmarkResult(
        item_id="item-1",
        validation_status="complete",
        judge_status="ok",
        outcome_score=0.9,
        alignment_score=0.8,
        trajectory_fidelity=0.7,
        ranking_metrics=RankingMetrics(mrr=0.5, map_score=0.4, ndcg_at_10=0.6),
    )
    degraded = BenchmarkResult(
        item_id="item-2",
        validation_status="complete",
        judge_status="degraded",
        outcome_score=0.2,
        trajectory_fidelity=0.3,
        ranking_metrics=RankingMetrics(ndcg_at_10=0.1),
    )

    variants = ["graph-full", "flat-chunk"]
    summaries = []
    for vid in variants:
        summaries.append(
            build_variant_summary(
                vid,
                [result, degraded],
                profiles_by_item={"item-1": "financebench", "item-2": "financebench"},
                relevance_by_item={"item-1": ["c1"], "item-2": ["c2"]},
                ground_truth_by_item={"item-1": {"answer": "a"}, "item-2": {"answer": "b"}},
            )
        )
    export = export_paper_tables(summaries, release_tag="paper-smoke")
    write_paper_tables(export, root)

    if bad_csv_header:
        (root / "tables" / "headline.csv").write_text("wrong,headers\n1,2\n", encoding="utf-8")

    repro_run = {
        "repro_run_id": "test-run-id",
        "release_tag": "paper-smoke",
        "manifest_hash": "sha256:abc",
        "started_at": "2026-06-01T10:00:00+00:00",
        "completed_at": "2026-06-01T10:05:00+00:00",
        "defer_judge": False,
        "variant_runs": [
            {
                "variant_id": vid,
                "mlflow_parent_run_id": f"mlflow-{vid}",
                "report_dir": f"reports/repro/{vid}",
                "items_excluded_incomplete": 0,
                "items_excluded_degraded": 1 if vid == "graph-full" else 0,
            }
            for vid in variants
        ],
        "status": "completed",
    }
    (root / "repro_run.json").write_text(json.dumps(repro_run), encoding="utf-8")
    (root / "export_manifest.json").write_text(
        json.dumps({"release_tag": "paper-smoke", "exported_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )
    (root / "tables" / "headline.tex").write_text("\\begin{table}stub\\end{table}\n", encoding="utf-8")

    if include_results:
        for vid in variants:
            if omit_variant and vid == omit_variant:
                continue
            vdir = root / vid
            vdir.mkdir(exist_ok=True)
            rows = [result, degraded]
            if vid == "flat-chunk":
                rows = [
                    result.model_copy(update={"outcome_score": 0.5, "trajectory_fidelity": 0.4}),
                    degraded,
                ]
            (vdir / "results.json").write_text(
                json.dumps([r.model_dump(mode="json") for r in rows]),
                encoding="utf-8",
            )

    return root
