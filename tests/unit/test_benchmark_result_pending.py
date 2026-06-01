"""BenchmarkResult pending judge status (013)."""

from __future__ import annotations

from models.evaluation import BenchmarkResult, JudgeStatus


def test_pending_judge_status_roundtrip() -> None:
    row = BenchmarkResult(item_id="x1", judge_status=JudgeStatus.PENDING.value)
    data = row.model_dump(mode="json")
    restored = BenchmarkResult.model_validate(data)
    assert restored.judge_status == "pending"
