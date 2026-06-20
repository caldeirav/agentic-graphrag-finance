"""Unit tests for diversity governance (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.judge_generator import _blocked_tickers_for_profile, _issuer_for_item
from evaluation.generation.review.diversity import append_duplicate_feedback, build_diversity_report
from models.benchmark_generation import DuplicateRejectionFeedback, GeneratedBenchmarkItem
from models.evaluation import ExpectedBindings, GroundTruth


def test_duplicate_feedback_record_shape(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    draft.mkdir()
    append_duplicate_feedback(
        draft,
        DuplicateRejectionFeedback(
            rejected_question="What is revenue?",
            matched_item_id="v2-financebench-0001",
            inspiration_profile="financebench",
            issuer_ticker="CAT",
            similarity_score=0.92,
        ),
    )
    row = json.loads((draft / "duplicate_feedback.jsonl").read_text().strip())
    assert row["matched_item_id"] == "v2-financebench-0001"
    assert row["issuer_ticker"] == "CAT"


def test_blocked_tickers_for_profile_issuer_cap() -> None:
    counts = {("financebench", "CAT"): 8, ("financebench", "XOM"): 3}
    blocked = _blocked_tickers_for_profile("financebench", counts, cap=8)
    assert blocked == ["CAT"]


def test_diversity_report_duplicate_rate(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    (draft / "generation_report.json").write_text(
        json.dumps(
            {
                "candidates_total": 100,
                "rejections_by_reason": {"duplicate_question": 40},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    item = GeneratedBenchmarkItem(
        item_id="v2-financebench-0001",
        question="Q",
        question_type_tag="metrics",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="1"),
        expected_bindings=ExpectedBindings(accessions=["acc-a"]),
        expected_section_paths=["acc-a/Item7"],
        validation_status="accepted",
    )
    (draft / "items" / "dev.jsonl").write_text(item.model_dump_json() + "\n", encoding="utf-8")
    report = build_diversity_report(draft)
    assert report.duplicate_rejection_rate == 0.4


def test_issuer_for_item_from_accession_map() -> None:
    item = GeneratedBenchmarkItem(
        item_id="x",
        question="Q",
        question_type_tag="t",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="1"),
        expected_bindings=ExpectedBindings(accessions=["acc-a"]),
        expected_section_paths=["acc-a/Item7"],
    )
    assert _issuer_for_item(item, {"acc-a": "CAT"}) == "CAT"
