"""Unit tests for paper-v2.0 outcome smoke gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.reproduction.smoke_gate import (
    SmokeGateThresholds,
    build_stratified_smoke_ids,
    evaluate_smoke_gate,
    load_smoke_item_ids,
)
from models.evaluation import BenchmarkResult, JudgeVerdict, RankingMetrics


def _result(item_id: str, va: float, mrr: float, answer: str = "ok") -> BenchmarkResult:
    return BenchmarkResult(
        item_id=item_id,
        judge_verdict=JudgeVerdict(
            judge_model="mock",
            judge_version="v3",
            rationale="",
            scores={"value_alignment": va},
        ),
        ranking_metrics=RankingMetrics(mrr=mrr),
        answer={"text": answer, "citations": []},
    )


def test_load_smoke_item_ids_from_bundle() -> None:
    bundle = Path("data/benchmarks/custom-judge/v2.0.0")
    if not bundle.is_dir():
        pytest.skip("v2.0.0 bundle not present")
    ids = load_smoke_item_ids(bundle)
    assert 40 <= len(ids) <= 60


def test_smoke_gate_passes_healthy_subset(tmp_path: Path) -> None:
    rows = [_result(f"item-{i}", 0.5, 0.8) for i in range(10)]
    path = tmp_path / "results.json"
    path.write_text(json.dumps([r.model_dump(mode="json") for r in rows]))
    item_ids = [r.item_id for r in rows]
    result = evaluate_smoke_gate(
        path,
        item_ids,
        thresholds=SmokeGateThresholds(
            min_task_success=0.25,
            max_mrr_zero_share=0.35,
            max_mrr_ok_va_zero=5,
            max_abstention_like_share=0.25,
            min_items_with_va=5,
        ),
    )
    assert result.ok
    assert result.metrics.task_success == 0.5


def test_smoke_gate_fails_low_task_success(tmp_path: Path) -> None:
    rows = [_result(f"item-{i}", 0.0, 0.0, answer="cannot determine from evidence") for i in range(10)]
    path = tmp_path / "results.json"
    path.write_text(json.dumps([r.model_dump(mode="json") for r in rows]))
    item_ids = [r.item_id for r in rows]
    result = evaluate_smoke_gate(path, item_ids)
    assert not result.ok
    assert any("task_success" in f for f in result.failures)


def test_build_stratified_smoke_ids() -> None:
    bundle = Path("data/benchmarks/custom-judge/v2.0.0")
    if not bundle.is_dir():
        pytest.skip("v2.0.0 bundle not present")
    ids = build_stratified_smoke_ids(bundle, count=50)
    assert len(ids) == 50
    assert len(set(ids)) == 50
