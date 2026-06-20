"""Integration test for selective re-judge with bundle override (018)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from evaluation.reproduction.judge_batch import run_judge_batch
from models.benchmark_generation import GeneratedBenchmarkItem
from models.evaluation import AnswerPackage, BenchmarkItem, BenchmarkResult, ExpectedBindings, GroundTruth, JudgeVerdict


def _write_bundle(root: Path, items: list[GeneratedBenchmarkItem], version: str) -> None:
    (root / "items").mkdir(parents=True, exist_ok=True)
    (root / "items" / "dev.jsonl").write_text(
        "\n".join(item.model_dump_json() for item in items) + "\n",
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0.0",
                "version": version,
                "status": "published",
                "item_count": len(items),
                "items_hash": "sha256:test",
                "sampling_manifest_path": "sampling_manifest.json",
                "generation_config_path": "generation_config.yaml",
                "corpus_bundle": {
                    "snapshot_id": "snap",
                    "issuer_snapshots": [],
                    "corpus_root": "corpus",
                    "graph_node_index_path": "corpus/graph_node_index.json",
                },
                "generation_judge_version": "mock",
                "evaluation_judge_version": "mock",
                "profile_counts": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_judge_batch_bundle_override_item_filter(tmp_path: Path, monkeypatch) -> None:
    base_item = GeneratedBenchmarkItem(
        item_id="v2-financebench-0001",
        question="What is revenue?",
        question_type_tag="metrics",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="100"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"]),
        expected_section_paths=["acc-1/Item7"],
        validation_status="accepted",
    )
    override_item = base_item.model_copy(
        update={"ground_truth": GroundTruth(answer="200")},
    )

    bundle = tmp_path / "v2.0.0"
    override = tmp_path / "draft"
    _write_bundle(bundle, [base_item], "2.0.0")
    _write_bundle(override, [override_item], "2.0.0-draft")

    repro = tmp_path / "repro"
    variant = repro / "graph-full"
    variant.mkdir(parents=True)
    pending = BenchmarkResult(
        item_id="v2-financebench-0001",
        judge_status="ok",
        outcome_score=0.0,
        answer=AnswerPackage(text="agent answer", citations=[]),
    )
    (variant / "results.json").write_text(
        json.dumps([pending.model_dump(mode="json")]) + "\n",
        encoding="utf-8",
    )

    captured: list[BenchmarkItem] = []

    class FakePanel:
        def judge(self, item, answer, trajectory, *, variant_id: str):
            captured.append(item)
            return JudgeVerdict(
                judge_model="fake",
                judge_version="3.1.0",
                scores={"value_alignment": 1.0, "synthesis_grounding": 1.0},
            )

    stats = run_judge_batch(
        repro,
        bundle_root=bundle,
        split="dev",
        judge=FakePanel(),
        bundle_override=override,
        item_ids={"v2-financebench-0001"},
        force_rescore=True,
    )
    assert stats["judged"] == 1
    assert captured[0].ground_truth.answer == "200"
