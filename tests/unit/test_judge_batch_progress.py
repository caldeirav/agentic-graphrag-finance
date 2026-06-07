"""Unit tests for judge-batch progress reporting."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from evaluation.reproduction import judge_batch as jb_mod
from evaluation.reproduction.judge_batch import run_judge_batch
from models.evaluation import BenchmarkItem, BenchmarkResult, GroundTruth, JudgeVerdict
from models.query import AnswerPackage, EvidenceChunk


def _citation(item_id: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=f"doc-chunk-{item_id}",
        excerpt="fact",
        content_hash=f"hash-{item_id}",
    )


def _pending_row(item_id: str) -> BenchmarkResult:
    return BenchmarkResult(
        item_id=item_id,
        judge_status="pending",
        answer=AnswerPackage(text="a", citations=[_citation(item_id)]),
    )


def _v3_complete_scores() -> dict[str, float]:
    return {
        "trajectory_coherence": 1.0,
        "routing_decisions": 1.0,
        "retrieval_fidelity": 1.0,
        "synthesis_grounding": 1.0,
        "value_alignment": 1.0,
    }


def test_judge_batch_logs_plan_and_empty_complete(tmp_path: Path) -> None:
    variant = tmp_path / "graph-full"
    variant.mkdir()
    (variant / "results.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "i1",
                    "judge_status": "ok",
                    "judge_verdict": {
                        "judge_model": "g",
                        "judge_version": "v3",
                        "scores": _v3_complete_scores(),
                    },
                    "trajectory_snapshot": {
                        "evidence_chunks": [
                            {
                                "chunk_node_id": "c1",
                                "excerpt": "x",
                                "content_hash": "h",
                            }
                        ]
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text('{"version": "1.0.0"}', encoding="utf-8")
    items = bundle / "items"
    items.mkdir()
    (items / "dev.jsonl").write_text(
        json.dumps(
            {
                "item_id": "i1",
                "dataset": "custom-judge",
                "question": "q",
                "ground_truth": {"answer": "a"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    lines: list[str] = []
    stats = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        progress=lines.append,
    )
    assert stats["judged"] == 0
    assert any("nothing to do" in line or "0 pending" in line for line in lines)
    assert any("resume-skipped" in line for line in lines)


def test_judge_batch_no_variants_message(tmp_path: Path) -> None:
    lines: list[str] = []
    repro_out = tmp_path / "repro-out"
    repro_out.mkdir()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text('{"version": "1.0.0"}', encoding="utf-8")
    (bundle / "items").mkdir()
    (bundle / "items" / "dev.jsonl").write_text("", encoding="utf-8")
    stats = run_judge_batch(
        repro_out,
        bundle_root=bundle,
        split="dev",
        progress=lines.append,
    )
    assert "no variant directories" in "\n".join(lines)
    assert stats["judged"] == 0


def test_judge_batch_checkpoints_each_item_for_resume(tmp_path: Path, monkeypatch) -> None:
    variant = tmp_path / "graph-full"
    variant.mkdir()
    results_path = variant / "results.json"
    results_path.write_text(
        json.dumps([_pending_row("i1").model_dump(mode="json"), _pending_row("i2").model_dump(mode="json")]),
        encoding="utf-8",
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text('{"version": "2.0.0"}', encoding="utf-8")
    items = [
        BenchmarkItem(
            item_id="i1",
            dataset="custom-judge",
            question="q1",
            ground_truth=GroundTruth(answer="a"),
        ),
        BenchmarkItem(
            item_id="i2",
            dataset="custom-judge",
            question="q2",
            ground_truth=GroundTruth(answer="b"),
        ),
    ]
    monkeypatch.setattr(
        "evaluation.reproduction.judge_batch.CustomJudgeDataset",
        lambda **_: MagicMock(load_split=lambda _s: items),
    )

    calls = {"n": 0}

    def _judge(item, answer, trajectory, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("interrupted")
        return JudgeVerdict(
            judge_model="mock",
            judge_version="v3",
            scores=_v3_complete_scores(),
        )

    judge = MagicMock()
    judge.judge.side_effect = _judge
    monkeypatch.setattr(jb_mod, "with_transient_retry", lambda fn, **_: fn())

    stats = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        judge=judge,
        concurrency=1,
    )
    assert stats["judged"] == 1
    assert stats["failed"] == 1
    mid = json.loads(results_path.read_text(encoding="utf-8"))
    assert mid[0]["judge_status"] == "ok"
    assert mid[1]["judge_status"] == "pending"

    judge.judge.side_effect = lambda item, answer, trajectory, **kwargs: JudgeVerdict(
        judge_model="mock",
        judge_version="v3",
        scores=_v3_complete_scores(),
    )
    stats2 = run_judge_batch(
        tmp_path,
        bundle_root=bundle,
        split="dev",
        judge=judge,
        concurrency=1,
    )
    assert stats2["judged"] == 1
    assert stats2["skipped"] == 1
    final = json.loads(results_path.read_text(encoding="utf-8"))
    assert all(r["judge_status"] == "ok" for r in final)
