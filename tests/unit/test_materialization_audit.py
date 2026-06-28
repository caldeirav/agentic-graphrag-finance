"""Unit tests for materialization audit (019)."""

from __future__ import annotations

from evaluation.reproduction.investigation.materialization_audit import build_materialization_audit
from models.benchmark_generation import GeneratedBenchmarkItem, GroundTruth
from models.evaluation import BenchmarkResult, ExpectedBindings
from models.query import AnswerPackage, EvidenceChunk


def _item() -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": "v2-test-audit",
            "question": "Q?",
            "question_type_tag": "single-fact",
            "inspiration_profile": "financebench",
            "ground_truth": GroundTruth(answer="1"),
            "expected_bindings": ExpectedBindings(accessions=["acc-a"]),
            "expected_section_paths": ["acc-a/Item7", "acc-a/XBRL"],
            "validation_status": "accepted",
        }
    )


def test_binding_miss_when_expected_section_not_visited(tmp_path) -> None:
    result = BenchmarkResult.model_validate(
        {
            "item_id": "v2-test-audit",
            "answer": AnswerPackage(
                text="answer",
                citations=[
                    EvidenceChunk(
                        chunk_node_id="c1",
                        excerpt="x",
                        content_hash="h",
                        accession="acc-a",
                        section_id="Item1A",
                    )
                ],
            ),
        }
    )
    audit = build_materialization_audit(
        bundle_root=tmp_path,
        item=_item(),
        result=result,
    )
    assert audit.binding_miss is True
    assert "acc-a/Item1A" in audit.visited_section_paths
    assert "acc-a/Item7" in audit.expected_section_paths
