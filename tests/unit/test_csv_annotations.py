"""Unit tests for CSV annotation import (018)."""

from __future__ import annotations

import csv
from pathlib import Path

from evaluation.generation.review.csv_annotations import (
    build_annotation_sheet_rows,
    import_annotations_from_csv,
    list_boilerplate_comparison_items,
)
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


def _draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    boilerplate = GeneratedBenchmarkItem(
        item_id="v2-finagentbench-0001",
        question="Compare risks?",
        question_type_tag="cross-filing-comparison",
        answer_type=AnswerType.COMPARISON_STRUCTURED,
        inspiration_profile="finagentbench",
        ground_truth=GroundTruth(
            answer=(
                "Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K discuss "
                "geopolitical risks in Item 1A. Risk Factors."
            ),
            required_claims=["a", "b", "c"],
        ),
        expected_bindings=ExpectedBindings(accessions=["acc-a", "acc-b"]),
        expected_section_paths=["acc-a/Item1A", "acc-b/Item1A"],
        multi_filing_required=True,
        validation_status="accepted",
    )
    good = GeneratedBenchmarkItem(
        item_id="v2-financebench-0002",
        question="Revenue?",
        question_type_tag="metrics",
        answer_type=AnswerType.SHORT_LABEL,
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="100"),
        expected_bindings=ExpectedBindings(accessions=["acc-1"]),
        expected_section_paths=["acc-1/Item7"],
        validation_status="accepted",
    )
    (draft / "items" / "dev.jsonl").write_text(
        boilerplate.model_dump_json() + "\n" + good.model_dump_json() + "\n",
        encoding="utf-8",
    )
    return draft


def test_list_boilerplate_comparison_items(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    hits = list_boilerplate_comparison_items(draft)
    assert len(hits) == 1
    assert hits[0].item_id == "v2-finagentbench-0001"


def test_build_annotation_sheet_has_empty_reviewer_fields(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    rows = build_annotation_sheet_rows(draft, ["v2-finagentbench-0001"])
    assert rows[0]["failure_class"] == ""
    assert rows[0]["is_boilerplate_comparison"] == "yes"


def test_import_csv_creates_annotations(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    csv_path = tmp_path / "annotated.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "failure_class",
                "corpus_spot_check",
                "notes",
                "proposed_answer",
                "proposed_question",
                "apply",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_id": "v2-financebench-0002",
                "failure_class": "gt_wrong",
                "corpus_spot_check": "passed",
                "notes": "fix answer",
                "proposed_answer": "150",
                "proposed_question": "",
                "apply": "yes",
            }
        )
    result = import_annotations_from_csv(
        draft,
        csv_path,
        reviewer_id="tester",
        dry_run=False,
    )
    assert result.imported == 1
    assert (draft / "annotations.jsonl").is_file()
