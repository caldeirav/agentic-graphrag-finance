"""Unit tests for custom-judge v2.0 publish gates (017)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.generation.bundle import (
    build_scorability_report,
    check_publish_gates,
    validate_bundle_feasibility,
)
from evaluation.generation.bundle_version import is_v2_bundle
from models.benchmark_generation import (
    AnswerType,
    CorpusBundle,
    DatasetManifest,
    DatasetStatus,
    GeneratedBenchmarkItem,
    GenerationReport,
)


def _item(
    item_id: str,
    *,
    answer: str | None = "42",
    answer_type: AnswerType | None = AnswerType.NUMERIC,
    tag: str = "metrics-generated",
    accessions: list[str] | None = None,
    required_claims: list[str] | None = None,
    multi_filing: bool = False,
) -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem.model_validate(
        {
            "item_id": item_id,
            "dataset": "custom-judge",
            "question": "What is revenue?",
            "question_type_tag": tag,
            "answer_type": answer_type.value if answer_type else None,
            "inspiration_profile": "financebench",
            "ground_truth": {
                "answer": answer,
                "required_claims": required_claims,
            },
            "expected_bindings": {"accessions": accessions or ["0000320193-24-000123"]},
            "expected_section_paths": ["0000320193-24-000123/item_7"],
            "multi_filing_required": multi_filing,
            "operation_class": "QUALITATIVE",
            "validation_status": "accepted",
            "validation_errors": [],
        }
    )


def _v2_manifest(item_count: int = 200) -> DatasetManifest:
    return DatasetManifest(
        schema_version="2.0.0",
        version="2.0.0",
        status=DatasetStatus.DRAFT,
        item_count=item_count,
        items_hash="sha256:test",
        sampling_manifest_path="sampling_manifest.json",
        generation_config_path="generation_config.yaml",
        corpus_bundle=CorpusBundle(
            snapshot_id="snap",
            issuer_snapshots=[],
            corpus_root="corpus",
            graph_node_index_path="corpus/graph_node_index.json",
            total_bytes=0,
        ),
        generation_judge_version="gemini",
        evaluation_judge_version="gemini",
        profile_counts={"financebench": item_count},
    )


def test_is_v2_bundle_semver() -> None:
    assert is_v2_bundle("2.0.0")
    assert not is_v2_bundle("1.2.0")


def test_scorability_rubric_only_zero_for_v2_items() -> None:
    items = [_item(f"v2-fin-{i:03d}") for i in range(3)]
    report = build_scorability_report(items)
    assert report["rubric_only_count"] == 0
    assert report["answer_gt_coverage"] == 1.0


def test_missing_answer_gt_blocked_in_feasibility(tmp_path: Path) -> None:
    items_path = tmp_path / "items" / "dev.jsonl"
    items_path.parent.mkdir(parents=True)
    bad = _item("v2-bad-001", answer="")
    items_path.write_text(bad.model_dump_json() + "\n", encoding="utf-8")
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "graph_node_index.json").write_text(
        json.dumps({"paths": ["0000320193-24-000123/item_7"]}),
        encoding="utf-8",
    )
    manifest = _v2_manifest(item_count=1)
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    report = validate_bundle_feasibility(tmp_path, items_path, manifest=manifest)
    reasons = {b["reason"] for b in report["blocked_items"]}  # type: ignore[index]
    assert "missing_answer_gt" in reasons


def test_publish_gate_requires_answer_gt_coverage(tmp_path: Path) -> None:
    manifest = _v2_manifest()
    report = GenerationReport(
        run_id="r",
        candidates_total=200,
        accepted_count=200,
        rejected_count=0,
        pass_rate=1.0,
        judge_api_calls=0,
        storage_bytes_used=0,
        duration_seconds=1.0,
    )
    items_path = tmp_path / "items" / "dev.jsonl"
    items_path.parent.mkdir(parents=True)
    items = [_item(f"v2-fin-{i:03d}") for i in range(200)]
    items_path.write_text("\n".join(i.model_dump_json() for i in items) + "\n", encoding="utf-8")
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "graph_node_index.json").write_text(
        json.dumps({"paths": ["0000320193-24-000123/item_7"]}),
        encoding="utf-8",
    )
    (tmp_path / "scorability_report.json").write_text(
        json.dumps(build_scorability_report(items)),
        encoding="utf-8",
    )
    (tmp_path / "reachability_report.json").write_text(
        json.dumps({"unreachable_answer_gt_count": 0}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="multi_filing_count"):
        check_publish_gates(manifest, report, bundle_root=tmp_path, multi_filing_min=40)
