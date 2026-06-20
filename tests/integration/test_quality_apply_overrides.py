"""Integration test for apply-overrides workflow (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.overrides import apply_overrides
from models.benchmark_generation import (
    AnswerType,
    CorpusSpotCheckStatus,
    FailureClass,
    GeneratedBenchmarkItem,
    ProposedOverrides,
)
from models.evaluation import ExpectedBindings, GroundTruth


def test_extend_annotate_apply(tmp_path: Path) -> None:
    draft = tmp_path / "quality-draft"
    draft.mkdir()
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
    (draft / "manifest.json").write_text(
        json.dumps({"version": "2.0.0-draft", "schema_version": "2.0.0"}) + "\n",
        encoding="utf-8",
    )

    items = []
    for idx in range(3):
        items.append(
            GeneratedBenchmarkItem(
                item_id=f"v2-financebench-{idx:04d}",
                question=f"What is metric {idx}?",
                question_type_tag="metrics",
                answer_type=AnswerType.SHORT_LABEL,
                inspiration_profile="financebench",
                ground_truth=GroundTruth(answer=str(100 + idx)),
                expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=["FY2025"]),
                expected_section_paths=["acc-1/Item7"],
                validation_status="accepted",
            )
        )
    (draft / "items").mkdir()
    (draft / "items" / "dev.jsonl").write_text(
        "\n".join(item.model_dump_json() for item in items) + "\n",
        encoding="utf-8",
    )

    ann_ids = []
    for idx in range(3):
        ann = append_annotation(
            draft,
            item_id=f"v2-financebench-{idx:04d}",
            reviewer_id="operator",
            failure_class=FailureClass.GT_TOO_STRICT,
            corpus_spot_check=CorpusSpotCheckStatus.PASSED,
            proposed_overrides=ProposedOverrides(
                ground_truth=GroundTruth(answer=str(200 + idx)),
            ),
        )
        ann_ids.append(ann.annotation_id)

    changelog = apply_overrides(draft, annotation_ids=set(ann_ids))
    assert len(changelog) == 3
    assert all(entry.validation_outcome == "accepted" for entry in changelog)
    assert (draft / "override_changelog.jsonl").read_text(encoding="utf-8").count("\n") == 3
