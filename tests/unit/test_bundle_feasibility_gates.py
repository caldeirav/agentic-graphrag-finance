"""Unit tests for bundle v1.1.0 feasibility publish gates (016)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.generation.bundle import check_publish_gates, validate_bundle_feasibility
from models.benchmark_generation import (
    CorpusBundle,
    DatasetManifest,
    DatasetStatus,
    GeneratedBenchmarkItem,
    GenerationReport,
)


def _item(
    item_id: str,
    *,
    tag: str = "metrics-generated",
    answer: str | None = "42",
    rubric: str | None = None,
    accessions: list[str] | None = None,
    required_claims: list[str] | None = None,
) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": item_id,
            "dataset": "custom-judge",
            "question": "q",
            "question_type_tag": tag,
            "inspiration_profile": "financebench",
            "ground_truth": {
                "answer": answer,
                "rubric": rubric,
                "required_claims": required_claims,
            },
            "expected_bindings": {"accessions": accessions or ["0000320193-24-000123"]},
            "expected_section_paths": [],
            "relevant_chunk_ids": [],
            "multi_filing_required": False,
            "operation_class": "QUALITATIVE",
            "validation_status": "accepted",
            "validation_errors": [],
        }
    )


def _write_bundle(tmp_path: Path, items: list[GeneratedBenchmarkItem]) -> Path:
    root = tmp_path / "bundle"
    (root / "items").mkdir(parents=True)
    (root / "corpus").mkdir()
    lines = [json.dumps(i.model_dump(mode="json"), sort_keys=True) for i in items]
    (root / "items" / "dev.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "corpus" / "graph_node_index.json").write_text(
        json.dumps({"paths": ["0000320193-24-000123/Item7", "0000320193-24-000076/Item7"]}),
        encoding="utf-8",
    )
    return root


def _manifest_for(items: list[GeneratedBenchmarkItem]) -> DatasetManifest:
    return DatasetManifest(
        version="1.1.0-draft",
        status=DatasetStatus.DRAFT,
        item_count=len(items),
        items_hash="sha256:x",
        sampling_manifest_path="sampling_manifest.json",
        generation_config_path="generation_config.yaml",
        generation_judge_version="mock",
        evaluation_judge_version="mock",
        profile_counts={"financebench": len(items)},
        corpus_bundle=CorpusBundle(
            snapshot_id="test",
            issuer_snapshots=[],
            corpus_root="corpus",
            graph_node_index_path="corpus/graph_node_index.json",
            total_bytes=1,
        ),
    )


def test_comparison_bindings_blocked_with_single_accession(tmp_path: Path) -> None:
    root = _write_bundle(
        tmp_path,
        [_item("cmp-1", tag="agentic-multi-hop", answer=None, rubric="compare filings", accessions=["a1"])],
    )
    report = validate_bundle_feasibility(root, root / "items" / "dev.jsonl")
    assert report["blocked_count"] == 1
    assert report["blocked_items"][0]["reason"] == "comparison_bindings"  # type: ignore[index]


def test_reference_corpus_blocked_when_accession_missing(tmp_path: Path) -> None:
    root = _write_bundle(
        tmp_path,
        [
            _item(
                "ref-1",
                tag="reference-following",
                answer=None,
                rubric="cite filing",
                accessions=["missing-accession"],
            )
        ],
    )
    report = validate_bundle_feasibility(root, root / "items" / "dev.jsonl")
    assert any(b["reason"] == "reference_corpus" for b in report["blocked_items"])  # type: ignore[union-attr]


def test_required_claims_blocked_for_narrative_answer_gt(tmp_path: Path) -> None:
    root = _write_bundle(
        tmp_path,
        [_item("narr-1", answer="Long narrative answer without structured claims.")],
    )
    report = validate_bundle_feasibility(root, root / "items" / "dev.jsonl")
    assert any(b["reason"] == "required_claims" for b in report["blocked_items"])  # type: ignore[union-attr]


def test_check_publish_gates_raises_on_infeasible_bundle(tmp_path: Path) -> None:
    root = _write_bundle(
        tmp_path,
        [_item("cmp-1", tag="comparison", answer=None, rubric="r", accessions=["only-one"])],
    )
    manifest = _manifest_for(
        [
            _item("cmp-1", tag="comparison", answer=None, rubric="r", accessions=["only-one"]),
        ]
    )
    report = GenerationReport(
        run_id="r",
        candidates_total=1,
        accepted_count=1,
        rejected_count=0,
        pass_rate=1.0,
        judge_api_calls=0,
        storage_bytes_used=0,
        duration_seconds=0.0,
    )
    with pytest.raises(ValueError, match="infeasible"):
        check_publish_gates(manifest, report, min_items=1, skip_gates=False, bundle_root=root)
