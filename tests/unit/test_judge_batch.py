"""Judge batch idempotency (013)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from evaluation.reproduction.judge_batch import run_judge_batch
from models.evaluation import BenchmarkResult, GroundTruth, JudgeVerdict
from models.query import AnswerPackage, EvidenceChunk


def _citation(item_id: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=f"doc-chunk-{item_id}",
        excerpt="fact",
        content_hash=f"hash-{item_id}",
    )


def test_judge_batch_skips_final_status(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "items").mkdir(parents=True)
    (bundle / "manifest.json").write_text(
        json.dumps({"version": "0.0.1"}),
        encoding="utf-8",
    )
    (bundle / "items" / "dev.jsonl").write_text(
        json.dumps(
            {
                "item_id": "i1",
                "question": "q",
                "ground_truth": {"answer": "a"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    variant_dir = tmp_path / "graph-full"
    variant_dir.mkdir()
    results_path = variant_dir / "results.json"
    pending = BenchmarkResult(
        item_id="i1",
        judge_status="pending",
        answer=AnswerPackage(text="a", citations=[_citation("i1")]),
    )
    done = BenchmarkResult(
        item_id="i2",
        judge_status="ok",
        judge_verdict=JudgeVerdict(judge_model="m", judge_version="v2", scores={"x": 1.0}),
        trajectory_snapshot={"evidence_chunks": [_citation("i2").model_dump(mode="json")]},
    )
    results_path.write_text(
        json.dumps([pending.model_dump(mode="json"), done.model_dump(mode="json")]),
        encoding="utf-8",
    )

    judge = MagicMock()
    verdict = JudgeVerdict(judge_model="mock", judge_version="v2", scores={"synthesis_grounding": 0.9})
    judge.judge.return_value = verdict

    from models.evaluation import BenchmarkItem as BI

    item = BI(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        ground_truth=GroundTruth(answer="a"),
    )
    monkeypatch.setattr(
        "evaluation.reproduction.judge_batch.CustomJudgeDataset",
        lambda **_: MagicMock(load_split=lambda _s: [item]),
    )

    stats = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        judge=judge,
        concurrency=1,
    )
    assert stats["judged"] == 1
    assert judge.judge.call_count == 1
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    assert rows[0]["judge_status"] == "ok"
