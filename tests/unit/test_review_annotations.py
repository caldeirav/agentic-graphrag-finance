"""Unit tests for annotations sidecar (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.annotations import (
    append_annotation,
    latest_annotation,
    load_annotation_history,
)
from models.benchmark_generation import (
    CorpusSpotCheckStatus,
    FailureClass,
    ProposedOverrides,
)


def _draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    (draft / "items" / "dev.jsonl").write_text("{}\n", encoding="utf-8")
    return draft


def test_append_annotation_preserves_history(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    first = append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="alice",
        failure_class=FailureClass.GT_BOILERPLATE,
        notes="first",
    )
    second = append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="bob",
        failure_class=FailureClass.GT_WRONG,
        notes="second",
    )
    history = load_annotation_history(draft)
    assert len(history) == 2
    assert history[0].annotation_id == first.annotation_id
    assert history[1].annotation_id == second.annotation_id
    assert latest_annotation(draft, "v2-financebench-0001").failure_class == FailureClass.GT_WRONG


def test_append_annotation_with_proposed_overrides(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="alice",
        failure_class=FailureClass.GT_BOILERPLATE,
        corpus_spot_check=CorpusSpotCheckStatus.PASSED,
        proposed_overrides=ProposedOverrides(
            ground_truth={"answer": "Substantive compared conclusion."},
        ),
    )
    ann = latest_annotation(draft, "v2-financebench-0001")
    assert ann.proposed_overrides is not None
    assert ann.proposed_overrides.ground_truth is not None


def test_dev_jsonl_unchanged_after_annotate(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    before = (draft / "items" / "dev.jsonl").read_text(encoding="utf-8")
    append_annotation(
        draft,
        item_id="v2-financebench-0001",
        reviewer_id="alice",
        failure_class=FailureClass.QUESTION_AMBIGUOUS,
    )
    after = (draft / "items" / "dev.jsonl").read_text(encoding="utf-8")
    assert before == after
