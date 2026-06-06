"""Unit tests for trajectory/citation consistency on write (015)."""

from evaluation.reproduction.result_write import ensure_trajectory_citation_consistency
from models.evaluation import BenchmarkResult
from models.query import AnswerPackage, EvidenceChunk


def test_hydrates_evidence_from_citations() -> None:
    citation = EvidenceChunk(
        chunk_node_id="doc-0000320193-24-000123-html-a",
        excerpt="Revenue grew.",
        content_hash="abc",
    )
    result = BenchmarkResult(
        item_id="x",
        answer=AnswerPackage(text="answer", citations=[citation]),
        trajectory_snapshot={"query": "q"},
    )
    updated = ensure_trajectory_citation_consistency(result)
    chunks = updated.trajectory_snapshot["evidence_chunks"]
    assert len(chunks) == 1
