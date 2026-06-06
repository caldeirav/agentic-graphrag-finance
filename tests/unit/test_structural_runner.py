"""Unit tests for structural metrics wiring helpers (015)."""

from evaluation.reproduction.runner import _structural_metrics_for_variant
from evaluation.reproduction.structural_extract import build_structural_inputs
from models.evaluation import BenchmarkItem, BenchmarkResult, ExpectedBindings


def test_structural_metrics_non_zero_with_binding_hit() -> None:
    item = BenchmarkItem(
        item_id="i1",
        dataset="custom-judge",
        question="q",
        expected_bindings=ExpectedBindings(accessions=["0000320193-24-000123"]),
    )
    result = BenchmarkResult(
        item_id="i1",
        trajectory_snapshot={
            "evidence_chunks": [
                {"chunk_node_id": "doc-0000320193-24-000123-html-risk_factors-1"},
            ],
        },
    )
    metrics = _structural_metrics_for_variant([item], [result])
    assert metrics.accession_binding_accuracy == 1.0


def test_build_structural_inputs_maps_item_ids() -> None:
    result = BenchmarkResult(
        item_id="i1",
        trajectory_snapshot={"graph_traversal": [{"node_id": "doc-0000320193-24-000123-html-a"}]},
    )
    used, paths = build_structural_inputs([result])
    assert "0000320193-24-000123" in used["i1"]
    assert paths["i1"]
