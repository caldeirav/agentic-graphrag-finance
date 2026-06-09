"""Unit: judge-batch hydrates trajectory_snapshot from answer citations."""

from __future__ import annotations

import os

from evaluation.judges.gemini_panel import GeminiJudgePanel
from evaluation.reproduction.judge_batch import _judge_one
from models.enums import EvidenceSourceType
from models.evaluation import BenchmarkItem, BenchmarkResult, GroundTruth
from models.query import AnswerPackage, EvidenceChunk


def test_judge_one_hydrates_evidence_from_citations() -> None:
    os.environ["USE_MOCK_JUDGE"] = "1"
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="Which segment includes Braun?",
        ground_truth=GroundTruth(answer="Grooming"),
    )
    citation = EvidenceChunk(
        chunk_node_id="doc-x-html-business-1-body",
        excerpt="Braun is reported under the Grooming segment.",
        content_hash="abc",
        source_type=EvidenceSourceType.HTML,
        section_id="html-business-1",
    )
    result = BenchmarkResult(
        item_id="i1",
        answer=AnswerPackage(text="Grooming segment includes Braun.", citations=[citation]),
        trajectory_snapshot={},
    )
    updated = _judge_one(item, result, GeminiJudgePanel(), variant_id="graph-full")
    snapshot = updated.trajectory_snapshot or {}
    chunks = snapshot.get("evidence_chunks") or []
    assert chunks
    assert chunks[0]["chunk_node_id"] == citation.chunk_node_id
