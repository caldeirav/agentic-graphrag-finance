"""Unit tests for custom-judge v1.2.0 migration (016)."""

from pathlib import Path

from evaluation.generation.bundle import validate_bundle_feasibility, validate_section_reachability
from evaluation.generation.gt_classifier import is_numeric_answer_gt
from evaluation.generation.migrate_v1_1_0 import build_draft_from_parent as build_v1_1_draft
from evaluation.generation.migrate_v1_1_0 import load_items
from evaluation.generation.migrate_v1_2_0 import (
    align_question_to_binding_years,
    build_draft_from_parent,
    derive_short_label_claims,
    enhance_required_claims,
)
from models.benchmark_generation import ExpectedBindings, GeneratedBenchmarkItem
from models.enums import OperationClass
from models.evaluation import GroundTruth


def test_align_question_years_to_binding() -> None:
    q = "What were 2026 net sales in the 2025 annual report?"
    aligned, changed = align_question_to_binding_years(q, ["FY2025"])
    assert changed
    assert "2026" not in aligned
    assert "2025" in aligned


def test_short_label_claims_for_segment() -> None:
    claims = derive_short_label_claims("Grooming", "Which segment includes Braun?")
    assert len(claims) >= 2
    assert any("Grooming" in c for c in claims)


def test_enhance_required_claims_adds_claims() -> None:
    item = GeneratedBenchmarkItem(
        item_id="pg-1",
        dataset="custom-judge",
        question="Which segment includes Braun?",
        question_type_tag="retrieval-qa",
        inspiration_profile="financebench",
        ground_truth=GroundTruth(answer="Grooming"),
        expected_bindings=ExpectedBindings(
            accessions=["0000080424-25-000012"],
            fiscal_periods=["FY2025"],
        ),
        expected_section_paths=["0000080424-25-000012/business"],
        operation_class=OperationClass.QUALITATIVE,
    )
    updated, entry = enhance_required_claims(item)
    assert entry is not None
    assert len(updated.ground_truth.required_claims or []) >= 2


def test_migrated_fixture_draft_passes_gates(tmp_path: Path) -> None:
    parent = Path("tests/fixtures/custom_judge")
    v11 = tmp_path / "v1.1.0"
    build_v1_1_draft(parent, v11, parent_version="1.0.0")
    draft = tmp_path / "v1.2.0-draft"
    items, changelog = build_draft_from_parent(v11, draft, parent_version="1.1.0")
    report = validate_bundle_feasibility(draft, draft / "items" / "dev.jsonl")
    reach = validate_section_reachability(draft, draft / "items" / "dev.jsonl")
    assert report["blocked_count"] == 0
    assert reach["unreachable_answer_gt_count"] == 0
    assert len(items) == 3
    assert (draft / "reachability_report.json").is_file()


def test_published_v1_2_0_bundle_is_feasible() -> None:
    root = Path("data/benchmarks/custom-judge/v1.2.0")
    if not root.is_dir():
        return
    items_path = root / "items" / "dev.jsonl"
    report = validate_bundle_feasibility(root, items_path)
    reach = validate_section_reachability(root, items_path)
    assert report["blocked_count"] == 0
    assert reach["unreachable_answer_gt_count"] == 0
    migrated = load_items(items_path)
    answer_gt = [i for i in migrated if i.ground_truth.answer]
    for item in answer_gt:
        if item.ground_truth.answer and not is_numeric_answer_gt(item.ground_truth.answer):
            assert item.ground_truth.required_claims
