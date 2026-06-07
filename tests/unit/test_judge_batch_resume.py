"""Unit tests for judge-batch v2 resume gate (015)."""

from evaluation.reproduction import judge_batch as jb
from models.evaluation import BenchmarkResult, JudgeVerdict


def _result(*, judge_version: str = "v1", evidence: bool = True, status: str = "ok") -> BenchmarkResult:
    snap = (
        {"evidence_chunks": [{"chunk_node_id": "doc-0000320193-24-000123-html-a"}]}
        if evidence
        else {}
    )
    return BenchmarkResult(
        item_id="item-1",
        judge_status=status,
        judge_verdict=JudgeVerdict(judge_model="gemini", judge_version=judge_version, scores={}),
        trajectory_snapshot=snap,
    )


def test_skip_rescore_v2_with_evidence() -> None:
    assert jb._should_skip_rescore(_result(judge_version="v2", evidence=True)) is True


def test_no_skip_v2_without_evidence() -> None:
    assert jb._should_skip_rescore(_result(judge_version="v2", evidence=False)) is False


def test_no_skip_v1_even_with_evidence() -> None:
    assert jb._should_skip_rescore(_result(judge_version="v1", evidence=True)) is False


def test_pending_includes_ok_pre_v2() -> None:
    rows = [_result(judge_version="v1", status="ok")]
    assert jb._pending_results(rows, force_rescore=False) == rows


def test_force_rescore_includes_v2() -> None:
    rows = [_result(judge_version="v2", evidence=True)]
    assert jb._pending_results(rows, force_rescore=True) == rows
