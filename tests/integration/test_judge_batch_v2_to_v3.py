"""Integration test for v2 → v3 judge-batch re-judge (016)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evaluation.reproduction.judge_batch import run_judge_batch
from models.evaluation import BenchmarkResult, JudgeVerdict

ITEM_ID = "0.0.0-financebench-001"


@pytest.mark.integration
def test_v2_partial_verdicts_rejudged_to_v3(tmp_path: Path) -> None:
    os.environ["USE_MOCK_JUDGE"] = "1"
    bundle = Path("tests/fixtures/custom_judge")
    variant_dir = tmp_path / "graph-full"
    variant_dir.mkdir()
    row = BenchmarkResult(
        item_id=ITEM_ID,
        judge_status="ok",
        judge_verdict=JudgeVerdict(
            judge_model="gemini",
            judge_version="v2",
            scores={
                "trajectory_coherence": 1.0,
                "routing_decisions": 1.0,
                "retrieval_fidelity": 1.0,
                "synthesis_grounding": 1.0,
            },
        ),
        trajectory_snapshot={
            "evidence_chunks": [
                {
                    "chunk_node_id": "doc-html-a",
                    "excerpt": "net sales",
                    "content_hash": "abc",
                }
            ]
        },
    )
    results_path = variant_dir / "results.json"
    results_path.write_text(json.dumps([row.model_dump(mode="json")]), encoding="utf-8")

    stats = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        concurrency=1,
    )
    assert stats["judged"] == 1
    saved = json.loads(results_path.read_text(encoding="utf-8"))[0]
    verdict = saved["judge_verdict"]
    assert verdict["judge_version"] == "v3"
    assert "value_alignment" in verdict["scores"]


@pytest.mark.integration
def test_v3_rescore_populates_value_alignment_for_answer_gt_items(tmp_path: Path) -> None:
    """SC-004: answer-GT items receive value_alignment after v3 re-judge."""
    os.environ["USE_MOCK_JUDGE"] = "1"
    bundle = Path("tests/fixtures/custom_judge")
    variant_dir = tmp_path / "graph-full"
    variant_dir.mkdir()
    row = BenchmarkResult(
        item_id=ITEM_ID,
        judge_status="ok",
        judge_verdict=JudgeVerdict(
            judge_model="gemini",
            judge_version="v2",
            scores={"synthesis_grounding": 1.0},
        ),
        trajectory_snapshot={
            "evidence_chunks": [
                {
                    "chunk_node_id": "doc-html-a",
                    "excerpt": "net sales",
                    "content_hash": "abc",
                }
            ]
        },
    )
    results_path = variant_dir / "results.json"
    results_path.write_text(json.dumps([row.model_dump(mode="json")]), encoding="utf-8")

    run_judge_batch(tmp_path, bundle_root=bundle, split="dev", concurrency=1)
    saved = json.loads(results_path.read_text(encoding="utf-8"))[0]
    assert "value_alignment" in saved["judge_verdict"]["scores"]
