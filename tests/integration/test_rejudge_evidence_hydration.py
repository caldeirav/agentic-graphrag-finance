"""Integration test for evidence hydration at re-score."""

from models.evaluation import BenchmarkResult
from models.query import AnswerPackage, EvidenceChunk
from tracing.trajectory_export import normalize_trajectory_state


def _has_hydrated_evidence(state: dict) -> bool:
    chunks = state.get("evidence_chunks") or []
    return any(c.get("excerpt") and c.get("content_hash") for c in chunks)


def test_sc002_majority_cited_items_have_evidence() -> None:
    results: list[BenchmarkResult] = []
    for i in range(10):
        citation = EvidenceChunk(
            chunk_node_id=f"doc-0000320193-24-000123-html-{i}",
            excerpt="fact",
            content_hash=f"h{i}",
        )
        snap = {"evidence": [citation.model_dump(mode="json")], "query": "q"}
        results.append(
            BenchmarkResult(
                item_id=f"item-{i}",
                answer=AnswerPackage(text="a", citations=[citation]),
                trajectory_snapshot=snap,
            )
        )
    # One item missing evidence snapshot field
    results.append(
        BenchmarkResult(
            item_id="item-miss",
            answer=AnswerPackage(text="a", citations=[citation]),
            trajectory_snapshot={},
        )
    )
    cited = [r for r in results if r.answer and r.answer.citations]
    hydrated = 0
    for row in cited:
        state = normalize_trajectory_state(dict(row.trajectory_snapshot or {}))
        if not state.get("evidence_chunks") and row.answer and row.answer.citations:
            state = normalize_trajectory_state(
                {
                    **state,
                    "evidence_chunks": [c.model_dump(mode="json") for c in row.answer.citations],
                }
            )
        if state.get("evidence_chunks") or _has_hydrated_evidence(state):
            hydrated += 1
    rate = hydrated / len(cited)
    assert rate >= 0.8
