"""Judge-batch restart after simulated failure (013 SC-002)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from evaluation.reproduction import judge_batch as jb_mod
from evaluation.reproduction.judge_batch import run_judge_batch
from models.evaluation import BenchmarkItem, BenchmarkResult, JudgeVerdict


@pytest.mark.integration
def test_judge_batch_restart_only_pending_tail(tmp_path: Path, monkeypatch) -> None:
    bundle = Path("tests/fixtures/custom_judge")
    variant_dir = tmp_path / "graph-full"
    variant_dir.mkdir()
    rows = [BenchmarkResult(item_id=f"item-{i:02d}", judge_status="pending") for i in range(20)]
    results_path = variant_dir / "results.json"
    results_path.write_text(
        json.dumps([r.model_dump(mode="json") for r in rows]),
        encoding="utf-8",
    )

    items = [
        BenchmarkItem(item_id=f"item-{i:02d}", dataset="custom-judge", question=f"q{i}")
        for i in range(20)
    ]
    monkeypatch.setattr(
        "evaluation.reproduction.judge_batch.CustomJudgeDataset",
        lambda **_: MagicMock(load_split=lambda _s: items),
    )

    calls = {"n": 0}
    saved: dict[str, JudgeVerdict] = {}

    def _judge(item, answer, trajectory):
        calls["n"] += 1
        if calls["n"] > 10:
            raise RuntimeError("simulated crash")
        verdict = JudgeVerdict(
            judge_model="mock",
            judge_version="v1",
            scores={"synthesis_grounding": 0.8},
        )
        saved[item.item_id] = verdict
        return verdict

    judge = MagicMock()
    judge.judge.side_effect = _judge
    monkeypatch.setattr(jb_mod, "with_transient_retry", lambda fn, **_: fn())

    stats_first = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        judge=judge,
        concurrency=1,
    )
    assert stats_first["failed"] == 10
    mid = json.loads(results_path.read_text(encoding="utf-8"))
    assert sum(1 for r in mid if r["judge_status"] == "ok") == 10

    judge.judge.side_effect = lambda item, answer, trajectory: JudgeVerdict(
        judge_model="mock",
        judge_version="v1",
        scores={"synthesis_grounding": 0.8},
    )
    stats = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        judge=judge,
        concurrency=1,
    )
    assert stats["judged"] == 10
    final = json.loads(results_path.read_text(encoding="utf-8"))
    assert all(r["judge_status"] == "ok" for r in final)
    assert stats_first["judged"] + stats["judged"] == 20
