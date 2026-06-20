"""Unit tests for review overrides (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import append_annotation
from evaluation.generation.review.overrides import apply_overrides, item_content_hash
from models.benchmark_generation import (
    AnswerType,
    CorpusSpotCheckStatus,
    FailureClass,
    GeneratedBenchmarkItem,
    ProposedOverrides,
)
from models.evaluation import ExpectedBindings, GroundTruth


def _write_dev_item(draft: Path, item: GeneratedBenchmarkItem) -> None:
    (draft / "items").mkdir(parents=True, exist_ok=True)
    (draft / "items" / "dev.jsonl").write_text(item.model_dump_json() + "\n", encoding="utf-8")


def _financebench_item() -> GeneratedBenchmarkItem:
    return GeneratedBenchmarkItem(
        item_id="v2-financebench-0001",
        question="What is total revenue?",
        question_type_tag="metrics",
        answer_type=AnswerType.SHORT_LABEL,
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="100"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"], fiscal_periods=["FY2025"]),
        expected_section_paths=["acc-1/Item7"],
        validation_status="accepted",
    )


def _draft_bundle(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "corpus").mkdir()
    index = {"paths": ["acc-1/Item7"]}
    (draft / "corpus" / "graph_node_index.json").write_text(json.dumps(index) + "\n", encoding="utf-8")
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
    return draft


def test_item_content_hash_stable() -> None:
    item = _financebench_item()
    assert item_content_hash(item) == item_content_hash(item.model_copy())


def test_apply_overrides_dry_run(tmp_path: Path) -> None:
    draft = _draft_bundle(tmp_path)
    item = _financebench_item()
    _write_dev_item(draft, item)
    append_annotation(
        draft,
        item_id=item.item_id,
        reviewer_id="reviewer",
        failure_class=FailureClass.GT_TOO_STRICT,
        corpus_spot_check=CorpusSpotCheckStatus.PASSED,
        proposed_overrides=ProposedOverrides(
            ground_truth=GroundTruth(answer="150"),
        ),
    )
    changelog = apply_overrides(draft, dry_run=True)
    assert len(changelog) == 1
    assert changelog[0].validation_outcome == "accepted"
    reloaded = json.loads((draft / "items" / "dev.jsonl").read_text().strip())
    assert reloaded["ground_truth"]["answer"] == "100"


def test_apply_overrides_writes_changelog(tmp_path: Path) -> None:
    draft = _draft_bundle(tmp_path)
    item = _financebench_item()
    _write_dev_item(draft, item)
    ann = append_annotation(
        draft,
        item_id=item.item_id,
        reviewer_id="reviewer",
        failure_class=FailureClass.GT_WRONG,
        corpus_spot_check=CorpusSpotCheckStatus.PASSED,
        proposed_overrides=ProposedOverrides(
            question="Revised revenue question?",
            ground_truth=GroundTruth(answer="150"),
        ),
    )
    changelog = apply_overrides(draft, annotation_ids={ann.annotation_id})
    assert changelog[0].validation_outcome == "accepted"
    assert (draft / "override_changelog.jsonl").is_file()
    updated = json.loads((draft / "items" / "dev.jsonl").read_text().strip())
    assert updated["question"] == "Revised revenue question?"
    assert updated["ground_truth"]["answer"] == "150"
    assert (draft / "fixed_items.json").is_file()
    fixed = json.loads((draft / "fixed_items.json").read_text(encoding="utf-8"))
    assert fixed["item_ids"] == [item.item_id]
