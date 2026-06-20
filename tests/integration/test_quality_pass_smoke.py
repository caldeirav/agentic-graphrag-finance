"""End-to-end smoke test for quality-pass workflow (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.overrides import apply_overrides
from evaluation.generation.review.queue import build_review_queue
from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    FailureClass,
    GeneratedBenchmarkItem,
    ProposedOverrides,
)
from models.evaluation import ExpectedBindings, GroundTruth, RankingMetrics, BenchmarkResult


def _minimal_draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    (draft / "corpus").mkdir()
    (draft / "corpus" / "graph_node_index.json").write_text(
        json.dumps({"paths": ["acc-1/Item7"]}) + "\n",
        encoding="utf-8",
    )
    (draft / "sampling_manifest.json").write_text(
        json.dumps(
            {
                "manifest_id": "m",
                "config_hash": "c",
                "allowlist_hash": "a",
                "random_seed": 1,
                "selected_issuers": [{"ticker": "CAT", "accessions": ["acc-1"]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (draft / "manifest.json").write_text(json.dumps({"version": "1.0.0-draft"}) + "\n", encoding="utf-8")

    items = []
    for idx in range(3):
        items.append(
            GeneratedBenchmarkItem(
                item_id=f"v2-financebench-{idx:04d}",
                question=f"Revenue question {idx}?",
                question_type_tag="metrics",
                inspiration_profile="financebench",
                ground_truth=GroundTruth(answer=str(100 + idx)),
                expected_bindings=ExpectedBindings(accessions=["acc-1"]),
                expected_section_paths=["acc-1/Item7"],
                validation_status="accepted",
            )
        )
    (draft / "items" / "dev.jsonl").write_text(
        "\n".join(item.model_dump_json() for item in items) + "\n",
        encoding="utf-8",
    )
    return draft


def test_quality_pass_smoke_queue_annotate_apply_dry_run(tmp_path: Path) -> None:
    draft = _minimal_draft(tmp_path)
    repro = tmp_path / "repro"
    (repro / "graph-full").mkdir(parents=True)
    results = []
    for idx in range(3):
        results.append(
            BenchmarkResult(
                item_id=f"v2-financebench-{idx:04d}",
                outcome_score=0.0 if idx == 0 else 0.5,
                ranking_metrics=RankingMetrics(mrr=0.6 if idx == 0 else 0.1, ndcg_at_10=0.2),
            ).model_dump(mode="json")
        )
    (repro / "graph-full" / "results.json").write_text(json.dumps(results) + "\n", encoding="utf-8")

    queue = build_review_queue(draft, repro_input=repro)
    assert queue[0].priority_tier == 1

    append_annotation(
        draft,
        item_id="v2-financebench-0000",
        reviewer_id="smoke",
        failure_class=FailureClass.GT_TOO_STRICT,
        corpus_spot_check=CorpusSpotCheckStatus.PASSED,
        proposed_overrides=ProposedOverrides(
            ground_truth=GroundTruth(answer="150"),
        ),
    )
    changelog = apply_overrides(draft, dry_run=True)
    assert len(changelog) == 1
    assert changelog[0].validation_outcome == "accepted"
